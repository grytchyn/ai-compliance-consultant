import uuid
import logging
from fastapi import FastAPI, Form, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Submission
from .llm import call_ollama
from .search import duckduckgo_instant_answer
from .prompts import build_user_prompt, SYSTEM_PROMPT
from .utils import render_report, save_report
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Compliance Consultant")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

async def process_submission(sub_id: str, company: str, url: str, description: str, email: str):
    db = SessionLocal()
    try:
        logger.info(f"Processing submission {sub_id} for {company}")
        sub = db.query(Submission).filter(Submission.id == sub_id).first()
        if not sub:
            logger.error(f"Submission {sub_id} not found")
            return
        # Search
        logger.info(f"Searching for {company}")
        search_results = await duckduckgo_instant_answer(company)
        logger.info(f"Search results: {len(search_results)} items")
        search_text = "\n".join([r.get("content", "") for r in search_results if r.get("content")])
        # Build prompt
        logger.info("Building prompt")
        user_prompt = build_user_prompt(company, url, description, search_text)
        full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
        # Call LLM
        logger.info("Calling Ollama")
        report_md = await call_ollama(full_prompt, temperature=0.2)
        logger.info(f"Report generated, length: {len(report_md)}")
        # Save report
        logger.info("Saving report")
        report_path = save_report(report_md, sub_id)
        sub.status = "completed"
        sub.report_path = report_path
        db.commit()
        logger.info(f"Submission {sub_id} completed, report at {report_path}")
    except Exception as e:
        logger.error(f"Submission {sub_id} failed: {str(e)}", exc_info=True)
        sub.status = "failed"
        db.commit()
    finally:
        db.close()