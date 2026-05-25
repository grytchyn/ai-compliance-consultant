import uuid
from fastapi import FastAPI, Form, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Submission
from .llm import call_ollama
from .search import duckduckgo_instant_answer
from .prompts import build_user_prompt, SYSTEM_PROMPT
from .utils import render_report, save_report
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Compliance Consultant")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health():
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/submit")
async def submit_form(
    background_tasks: BackgroundTasks,
    company: str = Form(...),
    url: str = Form(""),
    description: str = Form(""),
    email: str = Form(""),
    db: Session = Depends(get_db)
):
    sub_id = str(uuid.uuid4())
    sub = Submission(
        id=sub_id,
        company=company,
        url=url,
        description=description,
        email=email,
        status="processing"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    background_tasks.add_task(process_submission, sub_id, company, url, description, email)
    return {"id": sub_id, "status": "processing"}

@app.get("/report/{sub_id}")
async def get_report(sub_id: str, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.status != "completed" or not sub.report_path:
        return {"status": sub.status}
    return FileResponse(path=sub.report_path, media_type='text/markdown', filename=f"report_{sub_id}.md")

def process_submission(sub_id: str, company: str, url: str, description: str, email: str):
    db = SessionLocal()
    try:
        sub = db.query(Submission).filter(Submission.id == sub_id).first()
        if not sub:
            return
        # Search
        search_results = duckduckgo_instant_answer(company)
        search_text = "\n".join([r.get("content", "") for r in search_results if r.get("content")])
        # Build prompt
        user_prompt = build_user_prompt(company, url, description, search_text)
        full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
        # Call LLM
        report_md = call_ollama(full_prompt, temperature=0.2)
        # Save report
        report_path = save_report(report_md, sub_id)
        sub.status = "completed"
        sub.report_path = report_path
        db.commit()
    except Exception as e:
        sub.status = "failed"
        db.commit()
    finally:
        db.close()