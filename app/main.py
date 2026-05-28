import uuid
import logging
from typing import List
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
from .website_analyzer import analyze_website
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

@app.get("/analyze-url")
async def analyze_url(url: str = ""):
    """Auto-detect company info from URL without creating a submission."""
    from urllib.parse import urlparse
    result = {"company_name": "", "sector": "", "hq_location": "", "page_title": ""}
    if not url.strip():
        return result
    try:
        # Use website_analyzer
        from .website_analyzer import analyze_website
        wd = analyze_website(url)
        if wd.get("company_name"):
            result["company_name"] = wd["company_name"]
        if wd.get("sector"):
            result["sector"] = wd["sector"]
        if wd.get("hq_location"):
            result["hq_location"] = wd["hq_location"]
        if wd.get("page_title"):
            result["page_title"] = wd["page_title"]
    except Exception as e:
        logger.warning(f"URL analysis failed: {e}")
        # Fallback: extract from domain
        try:
            parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
            domain = parsed.netloc or parsed.path
            result["company_name"] = domain.replace("www.", "").split(".")[0].title()
        except:
            pass
    return result

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

@app.get("/imprint", response_class=HTMLResponse)
async def imprint_page():
    with open("static/imprint.html", "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page():
    with open("static/privacy.html", "r", encoding="utf-8") as f:
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
    company: str = Form(""),
    url: str = Form(""),
    company_size: str = Form(""),
    sector: str = Form(""),
    annual_revenue: str = Form(""),
    hq_location: str = Form(""),
    # AI system details
    ai_systems_count: str = Form(""),
    deployment_type: str = Form(""),
    decision_type: str = Form(""),
    risk_self_assessment: str = Form(""),
    # Multi-checkbox fields (receive as list, join with comma)
    ai_purpose: List[str] = Form([]),
    data_sources: List[str] = Form([]),
    model_types: List[str] = Form([]),
    human_oversight: List[str] = Form([]),
    explainability: List[str] = Form([]),
    existing_certifications: List[str] = Form([]),
    audit_types: List[str] = Form([]),
    # Technical (single value)
    training_data_origin: str = Form(""),
    data_retention: str = Form(""),
    # Compliance (single value)
    has_documentation: str = Form(""),
    dpo_appointed: str = Form(""),
    gdpr_compliant: str = Form(""),
    other_certifications: str = Form(""),
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
    
    # If company is empty, try to extract from URL
    if not company.strip() and url.strip():
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
            domain = parsed.netloc or parsed.path
            company = domain.replace("www.", "").split(".")[0].title()
        except:
            pass
    
    # Combine certifications from checkboxes + text field
    certs_parts = list(existing_certifications) if isinstance(existing_certifications, list) else []
    if other_certifications:
        certs_parts.append(other_certifications)
    combined_certs = ", ".join(filter(None, certs_parts))

    # Convert checkbox lists to comma-separated strings
    def join_list(v):
        if isinstance(v, list):
            return ", ".join(filter(None, v))
        return v
    
    sub = Submission(
        id=sub_id,
        status="processing",
        company=company or "Unknown Company",
        url=url,
        company_size=company_size,
        sector=sector,
        annual_revenue=annual_revenue,
        hq_location=hq_location,
        ai_systems_count=ai_systems_count,
        ai_purpose=join_list(ai_purpose),
        deployment_type=deployment_type,
        data_sources=join_list(data_sources),
        decision_type=decision_type,
        risk_self_assessment=risk_self_assessment,
        model_types=join_list(model_types),
        training_data_origin=training_data_origin,
        human_oversight=join_list(human_oversight),
        explainability=join_list(explainability),
        data_retention=data_retention,
        has_documentation=has_documentation,
        dpo_appointed=dpo_appointed,
        gdpr_compliant=gdpr_compliant,
        existing_certifications=combined_certs,
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
    """Calculate compliance score 0-100 with level and recommendations.
    Multi-variate formula weighting ALL form fields per EU AI Act logic."""
    score = 100
    details = {}
    
    # ═══ PENALTIES (risk-increasing factors) ═══
    
    # 1. High-risk categories: each checked = -12 points
    risk_fields = [
        'risk_biometrics', 'risk_critical_infra', 'risk_education',
        'risk_employment', 'risk_credit', 'risk_law_enforcement',
        'risk_migration', 'risk_justice', 'risk_democratic'
    ]
    risk_count = sum(1 for field in risk_fields if getattr(sub, field, False))
    risk_penalty = risk_count * 12
    score -= risk_penalty
    details['risk_categories'] = f"-{risk_penalty} ({risk_count} high-risk categories)"
    
    # 2. AI system volume
    ai_count = str(getattr(sub, 'ai_systems_count', '') or '')
    ai_penalty = 0
    if ai_count in ('4-10',):
        ai_penalty = 8
    elif ai_count == '10+':
        ai_penalty = 15
    elif ai_count in ('1-3',):
        ai_penalty = 3
    score -= ai_penalty
    details['ai_volume'] = f"-{ai_penalty} (AI systems: {ai_count or 'none'})"
    
    # 3. Decision type autonomy
    decision = str(getattr(sub, 'decision_type', '') or '')
    decision_penalty = 0
    if decision == 'fully-automated':
        decision_penalty = 12
    elif decision == 'human-in-loop':
        decision_penalty = 6
    elif decision == 'decision-support':
        decision_penalty = 3
    score -= decision_penalty
    details['decision_autonomy'] = f"-{decision_penalty} (decision type: {decision or 'none'})"
    
    # 4. Deployment risk: customer-facing = more regulatory impact
    deployment = str(getattr(sub, 'deployment_type', '') or '')
    deploy_penalty = 0
    if deployment == 'both':
        deploy_penalty = 8
    elif deployment in ('customer-facing', 'third-party'):
        deploy_penalty = 5
    score -= deploy_penalty
    details['deployment'] = f"-{deploy_penalty} (deployment: {deployment or 'none'})"
    
    # 5. Self-assessment alignment
    self_assess = str(getattr(sub, 'risk_self_assessment', '') or '')
    if self_assess == 'unacceptable':
        score -= 20
        details['self_assessment'] = '-20 (user self-assessed as unacceptable risk)'
    elif self_assess == 'high':
        score -= 10
        details['self_assessment'] = '-10 (user self-assessed as high risk)'
    elif self_assess == 'uncertain':
        score -= 3
        details['self_assessment'] = '-3 (unsure about risk level)'
    else:
        details['self_assessment'] = '0'
    
    # 6. Lack of human oversight (if "none" or none selected)
    oversight = str(getattr(sub, 'human_oversight', '') or '')
    if 'none' in oversight or 'No human' in oversight or not oversight.strip():
        score -= 15
        details['human_oversight'] = '-15 (no human oversight in place)'
    elif oversight:
        oversight_count = len([o for o in oversight.replace(', ', ',').split(',') if o.strip()])
        if oversight_count <= 1:
            score -= 5
            details['human_oversight'] = '-5 (minimal oversight)'
        else:
            details['human_oversight'] = '0 (adequate oversight)'
    else:
        details['human_oversight'] = '0'
    
    # 7. No explainability
    explain = str(getattr(sub, 'explainability', '') or '')
    if 'not_applicable' in explain or 'None' in explain or not explain.strip():
        score -= 10
        details['explainability'] = '-10 (no explainability methods)'
    else:
        details['explainability'] = '0'
    
    # 8. Data retention
    retention = str(getattr(sub, 'data_retention', '') or '')
    if 'indefinite' in retention or 'No policy' in retention:
        score -= 8
        details['data_retention'] = '-8 (indefinite/no data retention policy)'
    elif 'not_sure' in retention:
        score -= 3
        details['data_retention'] = '-3 (unsure about data retention)'
    elif 'not_retained' in retention:
        details['data_retention'] = '0 (data not retained — good)'
    else:
        details['data_retention'] = '0'
    
    # 9. Training data risk
    training = str(getattr(sub, 'training_data_origin', '') or '')
    if 'public_web' in training:
        score -= 5
        details['training_data'] = '-5 (public web training data — higher provenance risk)'
    elif 'not_sure' in training:
        score -= 3
        details['training_data'] = '-3 (unsure about training data origin)'
    else:
        details['training_data'] = '0'
    
    # ═══ BONUSES (risk-mitigating factors) ═══
    bonus_total = 0
    
    # 1. Compliance documentation
    if getattr(sub, 'has_documentation', '') == "yes":
        bonus_total += 12
        details['documentation'] = '+12 (comprehensive documentation)'
    elif getattr(sub, 'has_documentation', '') == "partial":
        bonus_total += 5
        details['documentation'] = '+5 (partial documentation)'
    else:
        details['documentation'] = '0'
    
    # 2. DPO
    if getattr(sub, 'dpo_appointed', '') == "yes":
        bonus_total += 10
        details['dpo'] = '+10 (DPO appointed)'
    elif getattr(sub, 'dpo_appointed', '') == "planned":
        bonus_total += 3
        details['dpo'] = '+3 (DPO planned)'
    else:
        details['dpo'] = '0'
    
    # 3. GDPR
    if getattr(sub, 'gdpr_compliant', '') == "yes":
        bonus_total += 10
        details['gdpr'] = '+10 (GDPR compliant)'
    elif getattr(sub, 'gdpr_compliant', '') == "in_progress":
        bonus_total += 4
        details['gdpr'] = '+4 (GDPR in progress)'
    else:
        details['gdpr'] = '0'
    
    # 4. Certifications
    certs = str(getattr(sub, 'existing_certifications', '') or '')
    cert_items = [c.strip() for c in certs.replace(', ', ',').split(',') if c.strip() and c.strip() != 'none' and c.strip() != 'None yet']
    cert_bonus = min(len(cert_items) * 4, 12)
    if cert_bonus > 0:
        bonus_total += cert_bonus
        details['certifications'] = f'+{cert_bonus} ({len(cert_items)} certifications)'
    else:
        details['certifications'] = '0'
    
    # 5. Previous audits
    prev_audit = str(getattr(sub, 'previous_audits', '') or '')
    audit_types = str(getattr(sub, 'audit_types', '') or '')
    if prev_audit == 'yes' and audit_types.strip():
        audit_count = len([a for a in audit_types.replace(', ', ',').split(',') if a.strip()])
        audit_bonus = min(audit_count * 3, 9)
        bonus_total += audit_bonus
        details['audits'] = f'+{audit_bonus} ({audit_count} audit types completed)'
    elif prev_audit == 'yes':
        bonus_total += 3
        details['audits'] = '+3 (has had audits)'
    else:
        details['audits'] = '0'
    
    # 6. CE marking
    if getattr(sub, 'ce_marking', '') == "yes":
        bonus_total += 8
        details['ce_marking'] = '+8 (CE marking obtained)'
    elif getattr(sub, 'ce_marking', '') == "planned":
        bonus_total += 3
        details['ce_marking'] = '+3 (CE marking planned)'
    else:
        details['ce_marking'] = '0'
    
    # 7. Human oversight quality (bonus for multiple methods)
    if oversight and 'none' not in oversight and 'No human' not in oversight:
        methods = [o for o in oversight.replace(', ', ',').split(',') if o.strip()]
        if len(methods) >= 3:
            bonus_total += 5
            details['oversight_quality'] = '+5 (multiple oversight mechanisms)'
        elif len(methods) >= 1:
            details['oversight_quality'] = '0'
    
    # 8. Explainability bonus (having multiple methods)
    if explain and 'not_applicable' not in explain and 'None' not in explain:
        methods = [e for e in explain.replace(', ', ',').split(',') if e.strip()]
        if len(methods) >= 2:
            bonus_total += 5
            details['explainability_quality'] = '+5 (multiple explainability methods)'
        else:
            details['explainability_quality'] = '0'
    
    score += bonus_total
    
    # Clamp to 0-100
    score = max(0, min(100, score))
    
    # Determine level
    if score < 40:
        level = "high_risk"
    elif score <= 70:
        level = "medium"
    else:
        level = "low_risk"
    
    # ═══ GENERATE RECOMMENDATIONS ═══
    recommendations = []
    
    # High-risk category recommendations
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
    
    # Systemic gaps
    if getattr(sub, 'has_documentation', '') != "yes":
        recommendations.append("Maintain comprehensive technical documentation for AI systems (Art. 11-12)")
    if getattr(sub, 'dpo_appointed', '') != "yes":
        recommendations.append("Appoint a Data Protection Officer (DPO)")
    if getattr(sub, 'gdpr_compliant', '') != "yes":
        recommendations.append("Ensure GDPR compliance for AI data processing")
    if 'none' in oversight or 'No human' in oversight or not oversight.strip():
        recommendations.append("Implement human oversight mechanisms — manual review, approval workflow, or human-in-the-loop (Art. 14)")
    if 'not_applicable' in explain or 'None' in explain or not explain.strip():
        recommendations.append("Adopt explainability/interpretability methods (SHAP, LIME, feature importance) for transparency (Art. 13)")
    if decision == 'fully-automated':
        recommendations.append("Conduct fundamental rights impact assessment for fully automated decision systems (Art. 27)")
    if ai_count in ('4-10', '10+'):
        recommendations.append(f"Scale compliance management system — {ai_count} AI systems require structured governance framework")
    if 'indefinite' in retention or 'no policy' in retention.lower():
        recommendations.append("Define and implement a data retention policy aligned with GDPR Art. 5(1)(e)")
    
    # Positive reinforcement
    if risk_count == 0:
        recommendations.insert(0, "No high-risk AI categories flagged — maintaining this posture is key")
    if bonus_total >= 25:
        recommendations.append("Strong compliance foundation — continue monitoring regulatory updates")
    if not recommendations:
        recommendations.append("Continue maintaining current compliance posture")
    
    return {
        "score": score,
        "level": level,
        "recommendations": recommendations,
        "details": details
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
        
        # Website analysis
        website_data = {}
        company_url = str(sub.url or "")
        if company_url:
            logger.info(f"Analyzing website: {company_url}")
            try:
                website_data = await analyze_website(company_url)
                logger.info(f"Website analysis complete: {len(website_data.get('legal_pages', {}))} legal pages, "
                           f"{len(website_data.get('tech_stack', {}))} tech categories, "
                           f"{sum(1 for v in website_data.get('gdpr_signals', {}).values() if v)} GDPR signals, "
                           f"{sum(1 for v in website_data.get('ai_act_signals', {}).values() if v)} AI Act signals")
            except Exception as e:
                logger.error(f"Website analysis failed: {e}", exc_info=True)
                website_data = {"error": str(e)}
        
        # Search
        logger.info(f"Searching for {sub.company}")
        search_results = await duckduckgo_instant_answer(sub.company)
        logger.info(f"Search results: {len(search_results)} items")
        search_text = "\n".join([r.get("content", "") for r in search_results if r.get("content")])
        if not search_text:
            search_text = "No open-source data found."
        
        # Build enhanced prompt
        logger.info("Building enhanced prompt with all fields")
        full_prompt = build_enhanced_prompt(sub, search_text, sub.lang, website_data)
        
        # Add system prompt
        from .prompts import SYSTEM_PROMPT_EN
        full_prompt = SYSTEM_PROMPT_EN + "\n\n" + full_prompt
        
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
