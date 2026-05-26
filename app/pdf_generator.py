"""
PDF Report Generator for AI Compliance Consultant.

Uses WeasyPrint to render the report_pdf.html template with Jinja2,
fill in data from a submission, and convert to a beautiful PDF report.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from weasyprint import HTML

logger = logging.getLogger(__name__)

# Paths
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# Jinja2 environment
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def generate_pdf_report(sub_id: str, db: Session) -> str:
    """
    Generate a professional PDF compliance report for a submission.

    Args:
        sub_id: The submission ID (UUID string)
        db: SQLAlchemy database session

    Returns:
        Path to the generated PDF file as string.
    """
    from app.models import Submission

    # Fetch submission from database
    submission = db.query(Submission).filter(Submission.id == sub_id).first()
    if not submission:
        raise ValueError(f"Submission {sub_id} not found")

    # Calculate compliance score (reuse logic from main.py)
    score_data = _calculate_compliance_score(submission)
    compliance_score = score_data["score"]
    risk_level = score_data["level"]
    recommendations_raw = score_data["recommendations"]

    # Build template data
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")
    date_display = now.strftime("%d %B %Y")

    # Determine risk level label and class
    risk_level_map = {
        "high_risk": ("Critical Risk", "high"),
        "medium": ("Moderate Risk", "medium"),
        "low_risk": ("Low Risk", "low"),
    }
    risk_level_label, risk_level_class = risk_level_map.get(risk_level, ("Unknown", "medium"))

    # Key findings based on submission data
    key_findings = _build_key_findings(submission)

    # Count high-risk categories
    risk_category_names = submission.risk_categories_active()
    high_risk_count = len(risk_category_names)
    medium_risk_count = 0  # simplified

    # Compliance status label
    if compliance_score >= 80:
        compliance_status_label = "Substantially Compliant"
    elif compliance_score >= 40:
        compliance_status_label = "Partially Compliant"
    else:
        compliance_status_label = "Non-Compliant"

    # Detailed EU AI Act articles with status
    eu_ai_act_articles = _build_eu_ai_act_articles(submission, compliance_score)

    # Risk categories with status
    risk_categories = _build_risk_categories(submission)

    # Recommendations with priority/urgency
    recommendations = _build_recommendations(recommendations_raw, submission)

    # Render the template
    template = env.get_template("report_pdf.html")
    html_str = template.render(
        company=submission.company or "Unknown Company",
        sub_id=sub_id,
        generated_date=date_str,
        compliance_score=compliance_score,
        risk_level_label=risk_level_label,
        risk_level_class=risk_level_class,
        key_findings=key_findings,
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        compliance_status_label=compliance_status_label,
        recommendations=recommendations,
        eu_ai_act_articles=eu_ai_act_articles,
        risk_categories=risk_categories,
        # Company info for overview
        sector=submission.sector or "",
        company_size=submission.company_size or "",
        hq_location=submission.hq_location or "",
        ai_systems_count=submission.ai_systems_count or "",
        deployment_type=submission.deployment_type or "",
        date_display=date_display,
    )

    # Make sure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Convert HTML to PDF
    pdf_path = str(REPORTS_DIR / f"{sub_id}.pdf")
    HTML(string=html_str).write_pdf(pdf_path)

    logger.info(f"PDF report generated: {pdf_path}")
    return pdf_path


def _calculate_compliance_score(submission) -> dict:
    """Calculate compliance score 0-100 with level and recommendations."""
    score = 100

    # Risk checkboxes: each checked = -15 points
    risk_fields = [
        'risk_biometrics', 'risk_critical_infra', 'risk_education',
        'risk_employment', 'risk_credit', 'risk_law_enforcement',
        'risk_migration', 'risk_justice', 'risk_democratic'
    ]
    risk_count = sum(1 for field in risk_fields if getattr(submission, field, False))
    score -= risk_count * 15

    # Compliance status bonuses
    if getattr(submission, 'has_documentation', None) == "yes":
        score += 15
    if getattr(submission, 'dpo_appointed', None) == "yes":
        score += 10
    if getattr(submission, 'gdpr_compliant', None) == "yes":
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
        if getattr(submission, field, False):
            recommendations.append(rec)

    if getattr(submission, 'has_documentation', None) != "yes":
        recommendations.append("Maintain comprehensive technical documentation for AI systems")
    if getattr(submission, 'dpo_appointed', None) != "yes":
        recommendations.append("Appoint a Data Protection Officer (DPO)")
    if getattr(submission, 'gdpr_compliant', None) != "yes":
        recommendations.append("Ensure GDPR compliance for AI data processing")

    if not recommendations:
        recommendations.append("Continue maintaining current compliance posture")

    return {
        "score": score,
        "level": level,
        "recommendations": recommendations
    }


def _build_key_findings(submission) -> list:
    """Build key findings with type (pass/warn/fail/info) for the executive summary."""
    findings = []

    # Check risk categories
    risk_fields = [
        ('risk_biometrics', 'Biometric identification'),
        ('risk_critical_infra', 'Critical infrastructure'),
        ('risk_education', 'Education/vocational training'),
        ('risk_employment', 'Employment/worker management'),
        ('risk_credit', 'Credit assessment'),
        ('risk_law_enforcement', 'Law enforcement'),
        ('risk_migration', 'Migration/border control'),
        ('risk_justice', 'Administration of justice'),
        ('risk_democratic', 'Democratic processes'),
    ]
    active_risks = [name for field, name in risk_fields if getattr(submission, field, False)]
    if active_risks:
        findings.append({
            "type": "fail",
            "text": f"High-risk AI categories detected: {', '.join(active_risks[:3])}" + 
                    (f" and {len(active_risks) - 3} more" if len(active_risks) > 3 else "")
        })
    else:
        findings.append({
            "type": "pass",
            "text": "No high-risk AI categories detected under EU AI Act classification"
        })

    # Documentation check
    docs = getattr(submission, 'has_documentation', None)
    if docs == "yes":
        findings.append({"type": "pass", "text": "Technical documentation maintained for AI systems"})
    elif docs == "partial":
        findings.append({"type": "warn", "text": "Technical documentation is incomplete — risk of non-compliance with Art. 11"})
    else:
        findings.append({"type": "fail", "text": "No technical documentation found — required under EU AI Act Art. 11"})

    # DPO check
    dpo = getattr(submission, 'dpo_appointed', None)
    if dpo == "yes":
        findings.append({"type": "pass", "text": "Data Protection Officer (DPO) appointed"})
    else:
        findings.append({"type": "fail", "text": "Data Protection Officer (DPO) not appointed — may be required under Art. 17"})

    # GDPR check
    gdpr = getattr(submission, 'gdpr_compliant', None)
    if gdpr == "yes":
        findings.append({"type": "pass", "text": "GDPR compliant data processing procedures in place"})
    elif gdpr == "in_progress":
        findings.append({"type": "warn", "text": "GDPR compliance implementation in progress"})
    else:
        findings.append({"type": "fail", "text": "GDPR compliance not confirmed — essential for lawful AI data processing"})

    # AI systems count
    ai_count = getattr(submission, 'ai_systems_count', None)
    if ai_count and ai_count not in ("0", "none"):
        findings.append({"type": "info", "text": f"Organization uses {ai_count} AI system(s) requiring compliance assessment"})

    # Explainability
    expl = getattr(submission, 'explainability', None)
    if expl and expl.strip():
        findings.append({"type": "info", "text": f"AI explainability approach: {expl[:100]}"})

    # Ensure we have at least some findings
    if not findings:
        findings.append({"type": "info", "text": "Preliminary assessment completed. Further evaluation recommended."})

    return findings


def _build_eu_ai_act_articles(submission, compliance_score: int) -> list:
    """Map submission data to EU AI Act articles with compliance status."""
    articles = []

    arts = [
        {
            "article": "Art. 6-7",
            "requirement": "High-risk classification rules",
            "status_class": "compliant" if compliance_score >= 70 else ("partial" if compliance_score >= 40 else "noncompliant"),
            "status_label": "Compliant" if compliance_score >= 70 else ("Partial" if compliance_score >= 40 else "Non-Compliant"),
            "score": min(100, compliance_score + 5),
        },
        {
            "article": "Art. 8",
            "requirement": "Compliance requirements for high-risk systems",
            "status_class": "noncompliant" if any(getattr(submission, f, False) for f in ['risk_biometrics', 'risk_critical_infra']) else "compliant",
            "status_label": "Requires Action" if any(getattr(submission, f, False) for f in ['risk_biometrics', 'risk_critical_infra']) else "Compliant",
            "score": max(0, compliance_score - 10) if any(getattr(submission, f, False) for f in ['risk_biometrics', 'risk_critical_infra']) else min(100, compliance_score + 10),
        },
        {
            "article": "Art. 9",
            "requirement": "Risk management system",
            "status_class": "partial" if compliance_score < 80 else "compliant",
            "status_label": "Partial" if compliance_score < 80 else "Compliant",
            "score": compliance_score,
        },
        {
            "article": "Art. 10",
            "requirement": "Data and data governance",
            "status_class": getattr(submission, 'gdpr_compliant', None) == "yes" and "compliant" or "partial",
            "status_label": "Compliant" if getattr(submission, 'gdpr_compliant', None) == "yes" else "Partial",
            "score": 90 if getattr(submission, 'gdpr_compliant', None) == "yes" else 50,
        },
        {
            "article": "Art. 11",
            "requirement": "Technical documentation",
            "status_class": "compliant" if getattr(submission, 'has_documentation', None) == "yes" else ("partial" if getattr(submission, 'has_documentation', None) == "partial" else "noncompliant"),
            "status_label": "Compliant" if getattr(submission, 'has_documentation', None) == "yes" else ("Partial" if getattr(submission, 'has_documentation', None) == "partial" else "Non-Compliant"),
            "score": 90 if getattr(submission, 'has_documentation', None) == "yes" else (50 if getattr(submission, 'has_documentation', None) == "partial" else 10),
        },
        {
            "article": "Art. 12",
            "requirement": "Record-keeping and logging",
            "status_class": "partial",
            "status_label": "Partial",
            "score": max(0, compliance_score - 5),
        },
        {
            "article": "Art. 13",
            "requirement": "Transparency and provision of information",
            "status_class": "partial" if getattr(submission, 'explainability', None) else "noncompliant",
            "status_label": "Partial" if getattr(submission, 'explainability', None) else "Non-Compliant",
            "score": 60 if getattr(submission, 'explainability', None) else 20,
        },
        {
            "article": "Art. 14",
            "requirement": "Human oversight",
            "status_class": "compliant" if getattr(submission, 'human_oversight', None) and getattr(submission, 'human_oversight', '') != '' else "partial",
            "status_label": "Compliant" if getattr(submission, 'human_oversight', None) and getattr(submission, 'human_oversight', '') != '' else "Partial",
            "score": 85 if getattr(submission, 'human_oversight', None) and getattr(submission, 'human_oversight', '') != '' else 45,
        },
        {
            "article": "Art. 15",
            "requirement": "Accuracy, robustness, and cybersecurity",
            "status_class": "partial",
            "status_label": "Partial",
            "score": max(0, compliance_score - 5),
        },
        {
            "article": "Art. 17",
            "requirement": "Designation of DPO / responsible person",
            "status_class": "compliant" if getattr(submission, 'dpo_appointed', None) == "yes" else "noncompliant",
            "status_label": "Compliant" if getattr(submission, 'dpo_appointed', None) == "yes" else "Non-Compliant",
            "score": 90 if getattr(submission, 'dpo_appointed', None) == "yes" else 10,
        },
    ]

    return arts


def _build_risk_categories(submission) -> list:
    """Build risk categories from submission data."""
    categories = []
    mapping = {
        'risk_biometrics': ('Biometric Identification', 'Art. 6(2) + Annex III'),
        'risk_critical_infra': ('Critical Infrastructure', 'Art. 6(1) + Annex III'),
        'risk_education': ('Education & Vocational Training', 'Art. 6(1) + Annex III'),
        'risk_employment': ('Employment & Worker Management', 'Art. 6(1) + Annex III'),
        'risk_credit': ('Credit Assessment & Essential Services', 'Art. 6(1) + Annex III'),
        'risk_law_enforcement': ('Law Enforcement', 'Art. 6(2) + Annex III'),
        'risk_migration': ('Migration & Border Control', 'Art. 6(2) + Annex III'),
        'risk_justice': ('Administration of Justice', 'Art. 6(2) + Annex III'),
        'risk_democratic': ('Democratic Processes', 'Art. 6(2) + Annex III'),
    }
    for field, (name, ref) in mapping.items():
        if getattr(submission, field, False):
            categories.append({
                "name": name,
                "status": "Flagged - Requires Mitigation",
                "status_class": "noncompliant",
                "reference": ref,
            })

    if not categories:
        categories.append({
            "name": "General Purpose AI",
            "status": "Low Risk (Limited Transparency Obligations)",
            "status_class": "compliant",
            "reference": "Art. 52",
        })

    return categories


def _build_recommendations(recommendations_raw: list, submission) -> list:
    """Build structured recommendations with priority badges."""
    result = []

    priority_map = {
        "biometric": ("Critical", "critical"),
        "critical infrastructure": ("Critical", "critical"),
        "law enforcement": ("Critical", "critical"),
        "documentation": ("High", "high"),
        "DPO": ("High", "high"),
        "Data Protection Officer": ("High", "high"),
        "GDPR": ("High", "high"),
        "education": ("Medium", "medium"),
        "employment": ("Medium", "medium"),
        "credit": ("Medium", "medium"),
        "migration": ("High", "high"),
        "justice": ("High", "high"),
        "democratic": ("High", "high"),
        "maintain": ("Low", "low"),
        "continue": ("Low", "low"),
    }

    descriptions = {
        "Implement risk management for biometric identification systems": 
            "Deploy a comprehensive risk management framework specifically addressing remote biometric identification in public spaces, as required under EU AI Act high-risk classification.",
        "Address critical infrastructure AI risk categories": 
            "Implement risk mitigation measures for AI systems used in critical infrastructure management, including regular assessments and safety protocols.",
        "Mitigate risks in education and vocational training AI systems": 
            "Establish fairness and bias monitoring for AI systems determining access to education or evaluating learning outcomes.",
        "Address employment-related AI risk concerns": 
            "Ensure AI systems used for hiring, promotion, or worker evaluation comply with transparency and non-discrimination requirements.",
        "Implement safeguards for credit assessment AI systems": 
            "Deploy explainability and fairness controls for AI-driven credit scoring and essential services access decisions.",
        "Address law enforcement AI risk compliance requirements": 
            "Implement strict oversight, logging, and fundamental rights impact assessments for any law enforcement AI applications.",
        "Implement risk controls for migration and border control AI": 
            "Deploy safeguards ensuring fundamental rights protection in AI systems used for migration, asylum, and border management.",
        "Address risks in administration of justice AI systems": 
            "Ensure human oversight and transparency in AI systems supporting judicial decision-making or alternative dispute resolution.",
        "Mitigate risks to democratic processes from AI systems": 
            "Implement safeguards against AI-enabled manipulation in democratic processes, elections, and voter targeting.",
        "Maintain comprehensive technical documentation for AI systems": 
            "Create and maintain detailed technical documentation including system purpose, data sources, accuracy metrics, and risk assessments per Art. 11.",
        "Appoint a Data Protection Officer (DPO)": 
            "Designate a qualified Data Protection Officer to oversee data governance, compliance monitoring, and serve as primary contact for regulatory authorities.",
        "Ensure GDPR compliance for AI data processing": 
            "Review and align all AI data processing activities with GDPR requirements including data minimization, purpose limitation, and individual rights.",
        "Continue maintaining current compliance posture": 
            "Conduct regular compliance reviews and stay updated on evolving EU AI Act implementing regulations and delegated acts.",
    }

    for rec in recommendations_raw:
        # Determine priority
        priority = "Medium"
        priority_class = "medium"
        for keyword, (p, pc) in priority_map.items():
            if keyword.lower() in rec.lower():
                priority, priority_class = p, pc
                break

        desc = descriptions.get(rec, f"Review and address: {rec}")
        result.append({
            "title": rec,
            "description": desc,
            "priority": priority,
            "priority_class": priority_class,
        })

    return result
