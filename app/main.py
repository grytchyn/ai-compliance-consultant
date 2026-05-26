import uuid
import logging
from fastapi import FastAPI, Form, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Submission
from .llm import call_ollama
from .search import duckduckgo_instant_answer
from .prompts import build_user_prompt, build_enhanced_prompt
from .utils import save_report
import os
import json
import markdown
# Lazy import — weasyprint might not be installed on Render
# from .pdf_generator import generate_pdf_report

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Compliance Consultant")
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        content = f.read()
    return Response(content=content, media_type="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@app.get("/submit-page", response_class=HTMLResponse)
async def submit_page():
    with open("static/submit.html", "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@app.get("/result-page", response_class=HTMLResponse)
async def result_page():
    with open("static/result.html", "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@app.post("/submit")
async def submit_full(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Company info
    company: str = Form(...),
    url: str = Form(""),
    email: str = Form(""),
    company_size: str = Form(""),
    sector: str = Form(""),
    employees: str = Form(""),
    annual_revenue: str = Form(""),
    hq_location: str = Form(""),
    description: str = Form(""),
    # AI system details
    ai_systems_count: str = Form(""),
    ai_system_names: str = Form(""),
    ai_purpose: str = Form(""),
    deployment_type: str = Form(""),
    data_sources: str = Form(""),
    decision_type: str = Form(""),
    risk_self_assessment: str = Form(""),
    # Technical
    model_types: str = Form(""),
    training_data_origin: str = Form(""),
    human_oversight: str = Form(""),
    explainability: str = Form(""),
    data_retention: str = Form(""),
    # Compliance
    has_documentation: str = Form(""),
    dpo_appointed: str = Form(""),
    gdpr_compliant: str = Form(""),
    existing_certifications: str = Form(""),
    previous_audits: str = Form(""),
    ce_marking: str = Form(""),
    # Risk checkboxes
    risk_biometrics: bool = Form(False),
    risk_critical_infra: bool = Form(False),
    risk_education: bool = Form(False),
    risk_employment: bool = Form(False),
    risk_credit: bool = Form(False),
    risk_law_enforcement: bool = Form(False),
    risk_migration: bool = Form(False),
    risk_justice: bool = Form(False),
    risk_democratic: bool = Form(False),
    # Extra
    additional_info: str = Form("{}"),
    lang: str = Form("en"),
):
    sub_id = str(uuid.uuid4())
    
    # Parse additional_info JSON
    try:
        extra_json = json.loads(additional_info) if additional_info else {}
    except:
        extra_json = {}
    
    sub = Submission(
        id=sub_id,
        status="processing",
        company=company,
        url=url,
        email=email,
        company_size=company_size,
        sector=sector,
        employees=employees,
        annual_revenue=annual_revenue,
        hq_location=hq_location,
        description=description,
        ai_systems_count=ai_systems_count,
        ai_system_names=ai_system_names,
        ai_purpose=ai_purpose,
        deployment_type=deployment_type,
        data_sources=data_sources,
        decision_type=decision_type,
        risk_self_assessment=risk_self_assessment,
        model_types=model_types,
        training_data_origin=training_data_origin,
        human_oversight=human_oversight,
        explainability=explainability,
        data_retention=data_retention,
        has_documentation=has_documentation,
        dpo_appointed=dpo_appointed,
        gdpr_compliant=gdpr_compliant,
        existing_certifications=existing_certifications,
        previous_audits=previous_audits,
        ce_marking=ce_marking,
        risk_biometrics=risk_biometrics,
        risk_critical_infra=risk_critical_infra,
        risk_education=risk_education,
        risk_employment=risk_employment,
        risk_credit=risk_credit,
        risk_law_enforcement=risk_law_enforcement,
        risk_migration=risk_migration,
        risk_justice=risk_justice,
        risk_democratic=risk_democratic,
        additional_info=json.dumps(extra_json),
        lang=lang,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    
    background_tasks.add_task(process_submission, sub_id)
    return {"id": sub_id, "status": "processing"}

@app.get("/report/{sub_id}")
async def get_report(sub_id: str, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.status != "completed" or not sub.report_path:
        return {"status": sub.status}
    return FileResponse(path=sub.report_path, media_type='text/markdown', filename=f"report_{sub_id}.md")

def calculate_compliance_score(sub: Submission) -> dict:
    """Calculate compliance score 0-100 with level and recommendations."""
    score = 100
    
    # Risk checkboxes: each checked = -15 points
    risk_fields = [
        'risk_biometrics', 'risk_critical_infra', 'risk_education',
        'risk_employment', 'risk_credit', 'risk_law_enforcement',
        'risk_migration', 'risk_justice', 'risk_democratic'
    ]
    risk_count = sum(1 for field in risk_fields if getattr(sub, field, False))
    score -= risk_count * 15
    
    # Compliance status bonuses
    if sub.has_documentation == "yes":
        score += 15
    if sub.dpo_appointed == "yes":
        score += 10
    if sub.gdpr_compliant == "yes":
        score += 10
    
    # Clamp to 0-100
    score = max(0, min(100, score))
    
    # Determine level
    if score < 40:
        level = "high_risk"
    elif score <= 70:
        level = "medium"
    else:
        level = "low_risk"
    
    # Generate recommendations
    recommendations = []
    risk_labels = {
        'risk_biometrics': 'Implement risk management for biometric identification systems',
        'risk_critical_infra': 'Address critical infrastructure AI risk categories',
        'risk_education': 'Mitigate risks in education and vocational training AI systems',
        'risk_employment': 'Address employment-related AI risk concerns',
        'risk_credit': 'Implement safeguards for credit assessment AI systems',
        'risk_law_enforcement': 'Address law enforcement AI risk compliance requirements',
        'risk_migration': 'Implement risk controls for migration and border control AI',
        'risk_justice': 'Address risks in administration of justice AI systems',
        'risk_democratic': 'Mitigate risks to democratic processes from AI systems',
    }
    for field, rec in risk_labels.items():
        if getattr(sub, field, False):
            recommendations.append(rec)
    
    if sub.has_documentation != "yes":
        recommendations.append("Maintain comprehensive technical documentation for AI systems")
    if sub.dpo_appointed != "yes":
        recommendations.append("Appoint a Data Protection Officer (DPO)")
    if sub.gdpr_compliant != "yes":
        recommendations.append("Ensure GDPR compliance for AI data processing")
    
    if not recommendations:
        recommendations.append("Continue maintaining current compliance posture")
    
    return {
        "score": score,
        "level": level,
        "recommendations": recommendations
    }


@app.get("/report-score/{sub_id}")
async def get_report_score(sub_id: str, db: Session = Depends(get_db)):
    """Calculate and return compliance score 0-100."""
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    score_data = calculate_compliance_score(sub)
    return {
        "status": sub.status,
        **score_data
    }


@app.get("/download-pdf/{sub_id}")
async def download_pdf(sub_id: str, db: Session = Depends(get_db)):
    """Generate and download a professional PDF compliance report."""
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.status != "completed" or not sub.report_path:
        return {"status": sub.status, "error": "Report not ready yet"}
    
    try:
        from .pdf_generator import generate_pdf_report
        pdf_path = generate_pdf_report(sub_id, db)
        filename = f"AI_Compliance_Report_{sub.company.replace(' ', '_')}.pdf"
        return FileResponse(
            path=pdf_path, 
            media_type='application/pdf', 
            filename=filename,
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="PDF generation failed")


@app.get("/report-html/{sub_id}")
async def get_report_html(sub_id: str, db: Session = Depends(get_db)):
    """Return report as JSON with HTML-rendered content for the result page."""
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.status != "completed" or not sub.report_path:
        return {"status": sub.status, "html": ""}
    
    # Read the markdown report
    import markdown
    with open(sub.report_path, "r", encoding="utf-8") as f:
        md = f.read()
    html = markdown.markdown(md, extensions=['tables', 'fenced_code'])
    
    # Also extract summary/overview for preview
    summary = ""
    lines = md.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## ") or line.startswith("# "):
            summary += line + "\n"
            if i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith("#"):
                summary += lines[i+1][:200] + "\n\n"
            if len(summary) > 500:
                break
    
    # Calculate compliance score
    score_data = calculate_compliance_score(sub)
    
    return {
        "status": sub.status,
        "html": html,
        "markdown": md,
        "title": f"AI Compliance Report: {sub.company}",
        "company": sub.company,
        "summary": summary,
        **score_data
    }

async def process_submission(sub_id: str):
    db = SessionLocal()
    try:
        sub = db.query(Submission).filter(Submission.id == sub_id).first()
        if not sub:
            logger.error(f"Submission {sub_id} not found")
            return
        
        logger.info(f"Processing enhanced submission {sub_id} for {sub.company}")
        
        # Search
        logger.info(f"Searching for {sub.company}")
        search_results = await duckduckgo_instant_answer(sub.company)
        logger.info(f"Search results: {len(search_results)} items")
        search_text = "\n".join([r.get("content", "") for r in search_results if r.get("content")])
        if not search_text:
            search_text = "Данные из открытых источников не найдены."
        
        # Build enhanced prompt
        logger.info("Building enhanced prompt with all fields")
        full_prompt = build_enhanced_prompt(sub, search_text, sub.lang)
        
        # Add system prompt based on language
        from .prompts import SYSTEM_PROMPT_EN, SYSTEM_PROMPT_DE
        system = SYSTEM_PROMPT_EN if sub.lang == "en" else SYSTEM_PROMPT_DE
        full_prompt = system + "\n\n" + full_prompt
        
        # Call LLM
        logger.info("Calling Ollama with enhanced prompt")
        report_md = await call_ollama(full_prompt, temperature=0.2)
        logger.info(f"Report generated, length: {len(report_md)} chars")
        
        # Save report
        report_path = save_report(report_md, sub_id)
        sub.status = "completed"
        sub.report_path = report_path
        db.commit()
        logger.info(f"Enhanced submission {sub_id} completed, report at {report_path}")
    except Exception as e:
        logger.error(f"Submission {sub_id} failed: {str(e)}", exc_info=True)
        sub.status = "failed"
        db.commit()
    finally:
        db.close()

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

@app.post("/send-report-email")
async def send_report_email(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    sub_id = body.get("id")
    email = body.get("email")
    lang = body.get("lang", "en")
    
    if not sub_id or not email:
        raise HTTPException(status_code=400, detail="Missing id or email")
    
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub or not sub.report_path:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Read report
    with open(sub.report_path, "r", encoding="utf-8") as f:
        md = f.read()
    
    # For now: log the request (SMTP config needs user setup)
    logger.info(f"Email requested: report {sub_id} → {email} (lang={lang})")
    
    # Try to send via SMTP if configured
    smtp_host = os.getenv("SMTP_HOST", "")
    if smtp_host:
        try:
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_pass = os.getenv("SMTP_PASS", "")
            
            msg = MIMEMultipart()
            msg["Subject"] = f"AI Compliance Report: {sub.company}" if lang == "en" else f"KI-Compliance-Bericht: {sub.company}"
            msg["From"] = smtp_user
            msg["To"] = email
            
            html = markdown.markdown(md, extensions=['tables', 'fenced_code'])
            msg.attach(MIMEText(html, "html"))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            logger.info(f"Email sent: {sub_id} → {email}")
            return {"status": "sent", "email": email}
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return {"status": "logged", "message": "Email logged but SMTP not configured"}
    else:
        return {"status": "logged", "message": "SMTP not configured. Configure SMTP_HOST in env."}
