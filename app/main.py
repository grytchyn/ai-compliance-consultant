import uuid
import logging
from typing import List, Optional
from fastapi import FastAPI, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .database import SessionLocal, engine, Base, User
from .models import Submission
from .llm import call_ollama
from .search import duckduckgo_instant_answer
from .prompts import build_user_prompt, build_enhanced_prompt
from .utils import save_report
from .website_analyzer import analyze_website
from .auth import verify_google_token, login_or_register, get_current_user
from .auth import get_db as auth_get_db
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

# ── Auth endpoints ─────────────────────────────────────

@app.post("/auth/google")
async def auth_google(
    request: Request,
    db: Session = Depends(auth_get_db),
):
    """
    Exchange a Google ID token for a JWT session.
    Body: {"credential": "google_id_token"}
    """
    body = await request.json()
    credential = body.get("credential", "")
    if not credential:
        raise HTTPException(status_code=400, detail="Missing credential")

    google_data = verify_google_token(credential)
    if not google_data:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    user, token = login_or_register(google_data, db)
    return {
        "token": token,
        "user": user.to_dict(),
    }


@app.get("/auth/me")
async def auth_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(auth_get_db),
):
    """Get current authenticated user info."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Also fetch user's scan count
    scan_count = db.query(Submission).filter(Submission.user_id == current_user.id).count()
    user_data = current_user.to_dict()
    user_data["scan_count"] = scan_count
    return user_data


@app.post("/auth/save/{sub_id}")
async def auth_save_result(
    sub_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(auth_get_db),
):
    """Link an existing submission to the authenticated user."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    sub.user_id = current_user.id
    db.commit()
    return {"status": "ok", "message": "Result saved to your profile"}


@app.get("/auth/results")
async def auth_results(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(auth_get_db),
):
    """Get all scan results for the authenticated user."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .limit(50)
        .all()
    )
    
    results = []
    for sub in submissions:
        score = None
        level = None
        if sub.status == "completed":
            try:
                score_data = calculate_compliance_score(sub, sub.lang)
                score = score_data.get("score")
                level = score_data.get("level")
            except:
                pass
        
        results.append({
            "id": sub.id,
            "company": sub.company,
            "url": sub.url,
            "status": sub.status,
            "created_at": str(sub.created_at) if sub.created_at else None,
            "score": score,
            "level": level,
        })
    
    return {"results": results}

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

class SubmitRequest(BaseModel):
    company: str = ""
    url: str = ""
    company_size: str = ""
    sector: str = ""
    annual_revenue: str = ""
    hq_location: str = ""
    ai_systems_count: str = ""
    deployment_type: str = ""
    decision_type: str = ""
    risk_self_assessment: str = ""
    ai_purpose: list = []
    data_sources: list = []
    model_types: list = []
    human_oversight: list = []
    explainability: list = []
    existing_certifications: list = []
    audit_types: list = []
    training_data_origin: str = ""
    data_retention: str = ""
    has_documentation: str = ""
    dpo_appointed: str = ""
    gdpr_compliant: str = ""
    other_certifications: str = ""
    previous_audits: str = ""
    ce_marking: str = ""
    high_risk_categories: list = []
    additional_info: str = "{}"
    lang: str = "en"


@app.post("/submit")
async def submit_full(
    body: SubmitRequest,
    db: Session = Depends(get_db),
):

    # Get values from body
    ai_purpose_list = body.ai_purpose or []
    data_sources_list = body.data_sources or []
    model_types_list = body.model_types or []
    human_oversight_list = body.human_oversight or []
    explainability_list = body.explainability or []
    existing_certifications_list = body.existing_certifications or []
    audit_types_list = body.audit_types or []
    high_risk_list = body.high_risk_categories or []

    sub_id = str(uuid.uuid4())
    
    # Parse additional_info JSON
    try:
        extra_json = json.loads(body.additional_info) if body.additional_info else {}
    except:
        extra_json = {}
    
    # If company is empty, try to extract from URL
    company = body.company
    url = body.url
    if not company.strip() and url.strip():
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
            domain = parsed.netloc or parsed.path
            company = domain.replace("www.", "").split(".")[0].title()
        except:
            pass
    
    # Combine certifications from list + text field
    certs_parts = list(existing_certifications_list)
    if body.other_certifications:
        certs_parts.append(body.other_certifications)
    combined_certs = ", ".join(filter(None, certs_parts))

    # Risk booleans from multiselect
    risk_bio = "risk_biometrics" in high_risk_list
    risk_cri = "risk_critical_infra" in high_risk_list
    risk_edu = "risk_education" in high_risk_list
    risk_emp = "risk_employment" in high_risk_list
    risk_cre = "risk_credit" in high_risk_list
    risk_law = "risk_law_enforcement" in high_risk_list
    risk_mig = "risk_migration" in high_risk_list
    risk_jus = "risk_justice" in high_risk_list
    risk_dem = "risk_democratic" in high_risk_list

    sub = Submission(
        id=sub_id,
        status="processing",
        company=company or "Unknown Company",
        url=url,
        company_size=body.company_size,
        sector=body.sector,
        annual_revenue=body.annual_revenue,
        hq_location=body.hq_location,
        ai_systems_count=body.ai_systems_count,
        ai_purpose=", ".join(ai_purpose_list),
        deployment_type=body.deployment_type,
        data_sources=", ".join(data_sources_list),
        decision_type=body.decision_type,
        risk_self_assessment=body.risk_self_assessment,
        model_types=", ".join(model_types_list),
        training_data_origin=body.training_data_origin,
        human_oversight=", ".join(human_oversight_list),
        explainability=", ".join(explainability_list),
        data_retention=body.data_retention,
        has_documentation=body.has_documentation,
        dpo_appointed=body.dpo_appointed,
        gdpr_compliant=body.gdpr_compliant,
        existing_certifications=combined_certs,
        previous_audits=body.previous_audits,
        ce_marking=body.ce_marking,
        risk_biometrics=risk_bio,
        risk_critical_infra=risk_cri,
        risk_education=risk_edu,
        risk_employment=risk_emp,
        risk_credit=risk_cre,
        risk_law_enforcement=risk_law,
        risk_migration=risk_mig,
        risk_justice=risk_jus,
        risk_democratic=risk_dem,
        additional_info=json.dumps(extra_json),
        lang=body.lang,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    
    # Run in background via thread pool to avoid async issues
    import threading
    thread = threading.Thread(target=process_submission, args=(sub_id,), daemon=True)
    thread.start()
    return {"id": sub_id, "status": "processing"}

@app.get("/report/{sub_id}")
async def get_report(sub_id: str, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.status != "completed" or not sub.report_path:
        return {"status": sub.status}
    return FileResponse(path=sub.report_path, media_type='text/markdown', filename=f"report_{sub_id}.md")

def calculate_compliance_score(sub: Submission, lang: str = "en") -> dict:
    """Calculate compliance score 0-100 with level and recommendations.
    Multi-variate formula weighting ALL form fields per EU AI Act logic."""
    L = lambda en, de: de if lang == "de" else en
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
    details['risk_categories'] = f"-{risk_penalty} ({risk_count} {L('high-risk categories', 'Hochrisiko-Kategorien')})"
    
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
    details['ai_volume'] = f"-{ai_penalty} ({L('AI systems:', 'KI-Systeme:')} {ai_count or L('none', 'keine')})"
    
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
    details['decision_autonomy'] = f"-{decision_penalty} ({L('decision type:', 'Entscheidungsart:')} {decision or L('none', 'keine')})"
    
    # 4. Deployment risk: customer-facing = more regulatory impact
    deployment = str(getattr(sub, 'deployment_type', '') or '')
    deploy_penalty = 0
    if deployment == 'both':
        deploy_penalty = 8
    elif deployment in ('customer-facing', 'third-party'):
        deploy_penalty = 5
    score -= deploy_penalty
    details['deployment'] = f"-{deploy_penalty} ({L('deployment:', 'Einsatzart:')} {deployment or L('none', 'keine')})"
    
    # 5. Self-assessment alignment
    self_assess = str(getattr(sub, 'risk_self_assessment', '') or '')
    if self_assess == 'unacceptable':
        score -= 20
        details['self_assessment'] = f'-20 ({L("user self-assessed as unacceptable risk", "vom Nutzer als inakzeptables Risiko eingestuft")})'
    elif self_assess == 'high':
        score -= 10
        details['self_assessment'] = f'-10 ({L("user self-assessed as high risk", "vom Nutzer als hohes Risiko eingestuft")})'
    elif self_assess == 'uncertain':
        score -= 3
        details['self_assessment'] = f'-3 ({L("unsure about risk level", "Unsicherheit über Risikostufe")})'
    else:
        details['self_assessment'] = '0'
    
    # 6. Lack of human oversight (if "none" or none selected)
    oversight = str(getattr(sub, 'human_oversight', '') or '')
    if 'none' in oversight or 'No human' in oversight or not oversight.strip():
        score -= 15
        details['human_oversight'] = f'-15 ({L("no human oversight in place", "keine menschliche Aufsicht vorhanden")})'
    elif oversight:
        oversight_count = len([o for o in oversight.replace(', ', ',').split(',') if o.strip()])
        if oversight_count <= 1:
            score -= 5
            details['human_oversight'] = f'-5 ({L("minimal oversight", "minimale Aufsicht")})'
        else:
            details['human_oversight'] = f'0 ({L("adequate oversight", "ausreichende Aufsicht")})'
    else:
        details['human_oversight'] = '0'
    
    # 7. No explainability
    explain = str(getattr(sub, 'explainability', '') or '')
    if 'not_applicable' in explain or 'None' in explain or not explain.strip():
        score -= 10
        details['explainability'] = f'-10 ({L("no explainability methods", "keine Erklärbarkeitsmethoden")})'
    else:
        details['explainability'] = '0'
    
    # 8. Data retention
    retention = str(getattr(sub, 'data_retention', '') or '')
    if 'indefinite' in retention or 'No policy' in retention:
        score -= 8
        details['data_retention'] = f'-8 ({L("indefinite/no data retention policy", "unbegrenzt/keine Datenaufbewahrungsrichtlinie")})'
    elif 'not_sure' in retention:
        score -= 3
        details['data_retention'] = f'-3 ({L("unsure about data retention", "Unsicherheit über Datenaufbewahrung")})'
    elif 'not_retained' in retention:
        details['data_retention'] = f'0 ({L("data not retained — good", "Daten werden nicht aufbewahrt — gut")})'
    else:
        details['data_retention'] = '0'
    
    # 9. Training data risk
    training = str(getattr(sub, 'training_data_origin', '') or '')
    if 'public_web' in training:
        score -= 5
        details['training_data'] = f'-5 ({L("public web training data — higher provenance risk", "öffentliche Web-Trainingsdaten — höheres Herkunftsrisiko")})'
    elif 'not_sure' in training:
        score -= 3
        details['training_data'] = f'-3 ({L("unsure about training data origin", "Unsicherheit über Trainingsdaten-Herkunft")})'
    else:
        details['training_data'] = '0'
    
    # ═══ BONUSES (risk-mitigating factors) ═══
    bonus_total = 0
    
    # 1. Compliance documentation
    if getattr(sub, 'has_documentation', '') == "yes":
        bonus_total += 12
        details['documentation'] = f'+12 ({L("comprehensive documentation", "umfassende Dokumentation")})'
    elif getattr(sub, 'has_documentation', '') == "partial":
        bonus_total += 5
        details['documentation'] = f'+5 ({L("partial documentation", "teilweise Dokumentation")})'
    else:
        details['documentation'] = '0'
    
    # 2. DPO
    if getattr(sub, 'dpo_appointed', '') == "yes":
        bonus_total += 10
        details['dpo'] = f'+10 ({L("DPO appointed", "DSB bestellt")})'
    elif getattr(sub, 'dpo_appointed', '') == "planned":
        bonus_total += 3
        details['dpo'] = f'+3 ({L("DPO planned", "DSB geplant")})'
    else:
        details['dpo'] = '0'
    
    # 3. GDPR
    if getattr(sub, 'gdpr_compliant', '') == "yes":
        bonus_total += 10
        details['gdpr'] = f'+10 ({L("GDPR compliant", "DSGVO-konform")})'
    elif getattr(sub, 'gdpr_compliant', '') == "in_progress":
        bonus_total += 4
        details['gdpr'] = f'+4 ({L("GDPR in progress", "DSGVO in Bearbeitung")})'
    else:
        details['gdpr'] = '0'
    
    # 4. Certifications
    certs = str(getattr(sub, 'existing_certifications', '') or '')
    cert_items = [c.strip() for c in certs.replace(', ', ',').split(',') if c.strip() and c.strip() != 'none' and c.strip() != 'None yet']
    cert_bonus = min(len(cert_items) * 4, 12)
    if cert_bonus > 0:
        bonus_total += cert_bonus
        details['certifications'] = f'+{cert_bonus} ({len(cert_items)} {L("certifications", "Zertifizierungen")})'
    else:
        details['certifications'] = '0'
    
    # 5. Previous audits
    prev_audit = str(getattr(sub, 'previous_audits', '') or '')
    audit_types = str(getattr(sub, 'audit_types', '') or '')
    if prev_audit == 'yes' and audit_types.strip():
        audit_count = len([a for a in audit_types.replace(', ', ',').split(',') if a.strip()])
        audit_bonus = min(audit_count * 3, 9)
        bonus_total += audit_bonus
        details['audits'] = f'+{audit_bonus} ({audit_count} {L("audit types completed", "Audit-Typen durchgeführt")})'
    elif prev_audit == 'yes':
        bonus_total += 3
        details['audits'] = f'+3 ({L("has had audits", "hatte bereits Audits")})'
    else:
        details['audits'] = '0'
    
    # 6. CE marking
    if getattr(sub, 'ce_marking', '') == "yes":
        bonus_total += 8
        details['ce_marking'] = f'+8 ({L("CE marking obtained", "CE-Kennzeichnung erhalten")})'
    elif getattr(sub, 'ce_marking', '') == "planned":
        bonus_total += 3
        details['ce_marking'] = f'+3 ({L("CE marking planned", "CE-Kennzeichnung geplant")})'
    else:
        details['ce_marking'] = '0'
    
    # 7. Human oversight quality (bonus for multiple methods)
    if oversight and 'none' not in oversight and 'No human' not in oversight:
        methods = [o for o in oversight.replace(', ', ',').split(',') if o.strip()]
        if len(methods) >= 3:
            bonus_total += 5
            details['oversight_quality'] = f'+5 ({L("multiple oversight mechanisms", "mehrere Aufsichtsmechanismen")})'
        elif len(methods) >= 1:
            details['oversight_quality'] = '0'
    
    # 8. Explainability bonus (having multiple methods)
    if explain and 'not_applicable' not in explain and 'None' not in explain:
        methods = [e for e in explain.replace(', ', ',').split(',') if e.strip()]
        if len(methods) >= 2:
            bonus_total += 5
            details['explainability_quality'] = f'+5 ({L("multiple explainability methods", "mehrere Erklärbarkeitsmethoden")})'
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
    risk_labels_de = {
        'risk_biometrics': 'Risikomanagement für biometrische Identifikationssysteme implementieren',
        'risk_critical_infra': 'Hochrisiko-KI-Kategorien für kritische Infrastruktur adressieren',
        'risk_education': 'Risiken in KI-Systemen für Bildung und Berufsausbildung mindern',
        'risk_employment': 'Beschäftigungsbezogene KI-Risikobedenken adressieren',
        'risk_credit': 'Schutzmaßnahmen für KI-Kreditbewertungssysteme implementieren',
        'risk_law_enforcement': 'Compliance-Anforderungen für KI in der Strafverfolgung adressieren',
        'risk_migration': 'Risikokontrollen für KI in Migration und Grenzkontrolle implementieren',
        'risk_justice': 'Risiken in KI-Systemen der Rechtspflege adressieren',
        'risk_democratic': 'Risiken für demokratische Prozesse durch KI-Systeme mindern',
    }
    risk_labels_en = {
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
    risk_labels = risk_labels_de if lang == 'de' else risk_labels_en
    for field, rec in risk_labels.items():
        if getattr(sub, field, False):
            recommendations.append(rec)
    
    # Systemic gaps
    if getattr(sub, 'has_documentation', '') != "yes":
        recommendations.append(L("Maintain comprehensive technical documentation for AI systems (Art. 11-12)", "Umfassende technische Dokumentation für KI-Systeme führen (Art. 11-12)"))
    if getattr(sub, 'dpo_appointed', '') != "yes":
        recommendations.append(L("Appoint a Data Protection Officer (DPO)", "Datenschutzbeauftragten (DSB) bestellen"))
    if getattr(sub, 'gdpr_compliant', '') != "yes":
        recommendations.append(L("Ensure GDPR compliance for AI data processing", "DSGVO-Compliance für KI-Datenverarbeitung sicherstellen"))
    if 'none' in oversight or 'No human' in oversight or not oversight.strip():
        recommendations.append(L("Implement human oversight mechanisms — manual review, approval workflow, or human-in-the-loop (Art. 14)", "Menschliche Aufsichtsmechanismen implementieren — manuelle Prüfung, Genehmigungsworkflow oder Human-in-the-Loop (Art. 14)"))
    if 'not_applicable' in explain or 'None' in explain or not explain.strip():
        recommendations.append(L("Adopt explainability/interpretability methods (SHAP, LIME, feature importance) for transparency (Art. 13)", "Erklärbarkeits-/Interpretierbarkeitsmethoden (SHAP, LIME, Feature Importance) für Transparenz übernehmen (Art. 13)"))
    if decision == 'fully-automated':
        recommendations.append(L("Conduct fundamental rights impact assessment for fully automated decision systems (Art. 27)", "Grundrechte-Folgenabschätzung für vollautomatisierte Entscheidungssysteme durchführen (Art. 27)"))
    if ai_count in ('4-10', '10+'):
        recommendations.append(L(f"Scale compliance management system — {ai_count} AI systems require structured governance framework", f"Compliance-Management-System skalieren — {ai_count} KI-Systeme erfordern strukturierten Governance-Rahmen"))
    if 'indefinite' in retention or 'no policy' in retention.lower():
        recommendations.append(L("Define and implement a data retention policy aligned with GDPR Art. 5(1)(e)", "Datenaufbewahrungsrichtlinie gemäß DSGVO Art. 5(1)(e) definieren und implementieren"))
    
    # Positive reinforcement
    if risk_count == 0:
        recommendations.insert(0, L("No high-risk AI categories flagged — maintaining this posture is key", "Keine Hochrisiko-KI-Kategorien markiert — diese Haltung beibehalten ist entscheidend"))
    if bonus_total >= 25:
        recommendations.append(L("Strong compliance foundation — continue monitoring regulatory updates", "Starke Compliance-Grundlage — regulatorische Updates weiterverfolgen"))
    if not recommendations:
        recommendations.append(L("Continue maintaining current compliance posture", "Aktuelle Compliance-Haltung beibehalten"))
    
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
    score_data = calculate_compliance_score(sub, sub.lang if hasattr(sub, 'lang') else 'en')
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
        return {"status": sub.status, "html": "", "error_message": sub.error_message}
    
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
    score_data = calculate_compliance_score(sub, sub.lang if hasattr(sub, 'lang') else 'en')
    
    return {
        "status": sub.status,
        "html": html,
        "markdown": md,
        "title": f"{'KI-Compliance-Bericht' if sub.lang == 'de' else 'AI Compliance Report'}: {sub.company}",
        "company": sub.company,
        "summary": summary,
        **score_data
    }

def process_submission(sub_id: str):
    db = SessionLocal()
    try:
        sub = db.query(Submission).filter(Submission.id == sub_id).first()
        if not sub:
            logger.error(f"Submission {sub_id} not found")
            return
        
        logger.info(f"Processing enhanced submission {sub_id} for {sub.company}")
        
        # Website analysis (sync)
        website_data = {}
        company_url = str(sub.url or "")
        if company_url:
            logger.info(f"Analyzing website: {company_url}")
            try:
                website_data = analyze_website(company_url)
                logger.info(f"Website analysis complete for {company_url}")
            except Exception as e:
                logger.error(f"Website analysis failed: {e}", exc_info=True)
                website_data = {"error": str(e)}
        
        # Search (sync)
        logger.info(f"Searching for {sub.company}")
        try:
            search_results = duckduckgo_instant_answer(sub.company)
            logger.info(f"Search results: {len(search_results)} items")
            search_text = "\n".join([r.get("content", "") for r in search_results if r.get("content")])
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            search_text = "No open-source data found."
        if not search_text:
            search_text = "No open-source data found."
        
        # Build enhanced prompt
        logger.info("Building enhanced prompt with all fields")
        full_prompt = build_enhanced_prompt(sub, search_text, sub.lang, website_data)
        
        # Add system prompt in correct language
        from .prompts import get_system_prompt
        full_prompt = get_system_prompt(sub.lang) + "\n\n" + full_prompt
        
        # Call LLM (sync — no asyncio)
        logger.info("Calling Ollama with enhanced prompt")
        report_md = call_ollama(full_prompt, temperature=0.2)
        logger.info(f"Report generated, length: {len(report_md)} chars")
        
        # Save report
        report_path = save_report(report_md, sub_id)
        sub.status = "completed"
        sub.report_path = report_path
        db.commit()
        logger.info(f"Enhanced submission {sub_id} completed, report at {report_path}")
    except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Submission {sub_id} failed: {err_msg}", exc_info=True)
        sub.status = "failed"
        sub.error_message = err_msg
        db.commit()
    finally:
        db.close()
