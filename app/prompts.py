# System prompt for EU AI Act compliance analysis — English only

SYSTEM_PROMPT_EN = """You are an expert on the EU AI Act. High-risk AI systems include: biometric identification, critical infrastructure, employment, credit scoring, education. Key requirements: risk management, data governance, transparency, human oversight, logging, conformity assessment.
Respond strictly with facts from the provided context only, using markdown format.

Your response MUST be in ENGLISH. Use technical terms in English only."""

SYSTEM_PROMPT = SYSTEM_PROMPT_EN  # English always

def build_company_profile(submission, lang: str = "en") -> str:
    """Build structured company profile from submission data."""
    import json
    
    labels = {
        "en": {"company": "Company", "website": "Website", "size": "Company Size",
               "sector": "Sector", "employees": "Employees", "revenue": "Annual Revenue",
               "hq": "HQ Location", "not_specified": "Not specified", "ai_details": "AI System Details",
               "ai_count": "AI Systems in Production", "ai_names": "System Names",
               "ai_purpose": "AI Purpose", "deployment": "Deployment Type",
               "data_sources": "Data Sources", "decision_type": "Decision Type",
               "risk_self": "Risk Self-Assessment", "tech_details": "Technical Details",
               "model_types": "Model Types", "training_data": "Training Data Origin",
               "human_oversight": "Human Oversight", "explainability": "Explainability / Interpretability",
               "data_retention": "Data Retention Policy", "compliance_status": "Compliance Status",
               "documentation": "Documentation", "dpo": "DPO Appointed",
               "gdpr": "GDPR Compliant", "certifications": "Certifications",
               "audits": "Previous Audits", "ce_marking": "CE Marking",
               "high_risk": "High-Risk Categories (selected)", "none_selected": "None selected",
               "additional_info": "Additional Information", "ai_activity": "AI Activity Description",
               "yes": "Yes", "no": "No"},
    }
    L = labels["en"]
    ns = L["not_specified"]
    
    profile = []
    profile.append(f"**{L['company']}:** {submission.company or ns}")
    profile.append(f"**{L['website']}:** {submission.url or ns}")
    profile.append(f"**{L['size']}:** {submission.company_size or ns}")
    profile.append(f"**{L['sector']}:** {submission.sector or ns}")
    profile.append(f"**{L['employees']}:** {submission.employees or ns}")
    profile.append(f"**{L['revenue']}:** {submission.annual_revenue or ns}")
    profile.append(f"**{L['hq']}:** {submission.hq_location or ns}")
    profile.append(f"### {L['ai_details']}")
    profile.append(f"**{L['ai_count']}:** {submission.ai_systems_count or ns}")
    profile.append(f"**{L['ai_names']}:** {submission.ai_system_names or ns}")
    profile.append(f"**{L['ai_purpose']}:** {submission.ai_purpose or ns}")
    profile.append(f"**{L['deployment']}:** {submission.deployment_type or ns}")
    profile.append(f"**{L['data_sources']}:** {submission.data_sources or ns}")
    profile.append(f"**{L['decision_type']}:** {submission.decision_type or ns}")
    profile.append(f"**{L['risk_self']}:** {submission.risk_self_assessment or ns}")

    profile.append("")
    profile.append(f"### {L['tech_details']}")
    profile.append(f"**{L['model_types']}:** {submission.model_types or ns}")
    profile.append(f"**{L['training_data']}:** {submission.training_data_origin or ns}")
    profile.append(f"**{L['human_oversight']}:** {submission.human_oversight or ns}")
    profile.append(f"**{L['explainability']}:** {submission.explainability or ns}")
    profile.append(f"**{L['data_retention']}:** {submission.data_retention or ns}")

    profile.append("")
    profile.append(f"### {L['compliance_status']}")
    profile.append(f"**{L['documentation']}:** {submission.has_documentation or ns}")
    profile.append(f"**{L['dpo']}:** {submission.dpo_appointed or ns}")
    profile.append(f"**{L['gdpr']}:** {submission.gdpr_compliant or ns}")
    profile.append(f"**{L['certifications']}:** {submission.existing_certifications or ns}")
    profile.append(f"**{L['audits']}:** {submission.previous_audits or ns}")
    profile.append(f"**{L['ce_marking']}:** {submission.ce_marking or ns}")

    profile.append("")
    profile.append(f"### {L['high_risk']}")
    active = submission.risk_categories_active() if hasattr(submission, 'risk_categories_active') else []
    if active:
        for cat in active:
            profile.append(f"- [x] {cat}")
    else:
        profile.append(f"- {L['none_selected']}")

    # Additional info JSON
    if submission.additional_info:
        try:
            extra = json.loads(submission.additional_info)
            if extra:
                profile.append("")
                profile.append(f"### {L['additional_info']}")
                for k, v in extra.items():
                    profile.append(f"- **{k}:** {v}")
        except:
            pass

    profile.append("")
    if submission.description:
        profile.append(f"**{L['ai_activity']}:** {submission.description}")

    return "\n".join(profile)

def build_user_prompt(company: str, url: str, description: str, search_text: str, lang: str = "en") -> str:
    """Compatibility: build user prompt from simple fields."""
    if not search_text:
        search_text = "No open-source data found." if lang == "en" else "Keine öffentlichen Daten gefunden."
    sections_en = "\n".join([
        "Based on this data, determine:",
        "1) Does the product fall under a high-risk category? (Yes/No/Insufficient data).",
        "2) Which AI Act requirements are likely applicable (list).",
        "3) Identified gaps (what is missing for compliance).",
        "4) Specific recommendations (documents, processes, checkpoints).",
        "Format the answer in markdown with sections: **Conclusion**, **Risk Category**, **Applicable Requirements**, **Gaps**, **Recommendations**, **Sources**.",
        "If data is insufficient, indicate what information is needed."
    ])
    sections_de = "\n".join([
        "Bestimme auf Basis dieser Daten:",
        "1) Fällt das Produkt unter eine Hochrisiko-Kategorie? (Ja/Nein/Unzureichende Daten).",
        "2) Welche AI Act-Anforderungen sind wahrscheinlich anwendbar (Liste).",
        "3) Identifizierte Lücken (was fehlt zur Konformität).",
        "4) Konkrete Empfehlungen (Dokumente, Prozesse, Kontrollpunkte).",
        "Formatiere die Antwort in Markdown mit Abschnitten: **Fazit**, **Risikokategorie**, **Anwendbare Anforderungen**, **Lücken**, **Empfehlungen**, **Quellen**.",
        "Bei unzureichenden Daten: gib an, welche Informationen benötigt werden."
    ])
    sections = sections_en if lang == "en" else sections_de
    prompt = f"""Analyze the following company and its product for EU AI Act compliance.
Company: {company}
Website: {url}
Product description: {description}
Open-source data:
{search_text}
{sections}"""
    return prompt

def build_enhanced_prompt(submission, search_text: str = "", lang: str = "en", website_data: dict = None) -> str:
    """Build enhanced prompt from complete submission object with all fields.
    lang: 'en' or 'de'.
    website_data: dict from WebsiteAnalyzer.analyze()"""
    profile = build_company_profile(submission, lang)
    
    # Build website analysis section
    website_section = ""
    if website_data and "error" not in website_data:
        parts = []
        legal_pages = website_data.get("legal_pages", {})
        if legal_pages:
            pages_str = ", ".join(legal_pages.keys())
            parts.append(f"Legal pages found: {pages_str}")
        
        tech_stack = website_data.get("tech_stack", {})
        if tech_stack:
            tech_str = "; ".join(f"{k}: {', '.join(v)}" for k, v in tech_stack.items() if v)
            parts.append(f"Technology stack: {tech_str}")
        
        gdpr = website_data.get("gdpr_signals", {})
        gdpr_found = [k for k, v in gdpr.items() if v]
        if gdpr_found:
            parts.append(f"GDPR compliance signals detected: {', '.join(gdpr_found)}")
        
        ai_act = website_data.get("ai_act_signals", {})
        ai_act_found = [k for k, v in ai_act.items() if v]
        if ai_act_found:
            parts.append(f"EU AI Act disclosure signals detected: {', '.join(ai_act_found)}")
        
        chatbot = website_data.get("chatbot_detected")
        if chatbot:
            platform = website_data.get("chatbot_platform", "unknown")
            parts.append(f"Chatbot detected on website: {platform}")
        
        cmp = website_data.get("cmp_detected")
        if cmp:
            parts.append(f"Cookie consent management platform: {cmp}")
        
        company_info = website_data.get("company_info", {})
        if company_info:
            info_str = ", ".join(f"{k}: {v}" for k, v in company_info.items() if v)
            parts.append(f"Company info extracted: {info_str}")
        
        if parts:
            website_section = "\n## Website Analysis\n\n" + "\n".join(f"- {p}" for p in parts)
    
    # Build raw website data section — shows what data we scraped from the URL
    raw_website_section = ""
    if website_data:
        raw_parts = []
        scanned_url = website_data.get("url", str(submission.url or "N/A"))
        raw_parts.append(f"**Analyzed URL**: {scanned_url}")
        
        if website_data.get("page_title"):
            raw_parts.append(f"**Page title**: {website_data['page_title']}")
        if website_data.get("page_description"):
            raw_parts.append(f"**Meta description**: {website_data['page_description'][:200]}")
        if website_data.get("company_name"):
            raw_parts.append(f"**Detected company name**: {website_data['company_name']}")
        if website_data.get("sector"):
            raw_parts.append(f"**Detected industry**: {website_data['sector']}")
        if website_data.get("hq_location"):
            raw_parts.append(f"**Detected HQ location**: {website_data['hq_location']}")
        
        ai_uses = website_data.get("ai_use_cases", [])
        if ai_uses:
            raw_parts.append(f"**AI-related keywords found on website**: {', '.join(ai_uses[:8])}")
        
        if website_data.get("privacy_policy_url"):
            raw_parts.append(f"**Privacy policy found**: {website_data['privacy_policy_url']}")
        if website_data.get("has_cookie_banner"):
            raw_parts.append("**Cookie consent banner**: detected")
        gdpr = website_data.get("gdpr_signals", [])
        if gdpr:
            raw_parts.append(f"**GDPR signals**: {', '.join(gdpr[:5])}")
        
        if website_data.get("ai_disclosures"):
            raw_parts.append(f"**AI disclosure pages found**: {len(website_data['ai_disclosures'])}")
        
        if raw_parts:
            raw_website_section = "\n## Source Data (Scraped from Website)\n\n" + "\n".join(f"- {p}" for p in raw_parts)
    
    if not search_text:
        search_text = "No open-source data found."

    prompt = f"""Analyze the following company and its AI systems for EU AI Act compliance.

## Company Profile

{profile}

Open-source data:
{search_text}{website_section}{raw_website_section}

Based on all provided data, provide a SHORT, CONCISE compliance report.

IMPORTANT FORMAT RULES:
- MAXIMUM 3-4 sentences per section. No long paragraphs.
- Use short bullet points (max 5 per section), not long lists.
- NO tables unless absolutely necessary.
- Focus on the MOST CRITICAL findings only — don't list everything.
- The report should be EASY TO SCAN in 30 seconds.

Provide these sections:

## 1. OVERALL CONCLUSION (1-2 sentences only)
Is the company's activity regulated by the EU AI Act? What is the overall risk level?

## 2. KEY FINDINGS (3-5 bullet points max)
Most critical compliance issues found.

## 3. RISK LEVEL (one line)
Unacceptable / High / Limited / Minimal — with one sentence justification.

## 4. CRITICAL GAPS (3-5 bullet points max)
Only the most urgent compliance gaps.

## 5. TOP RECOMMENDATIONS (3-5 bullet points max)
Priority actions to take — ordered by urgency (immediate / short-term / long-term).

## 6. PENALTY RISK (1-2 sentences)
Potential fines and consequences if not addressed.

Keep the entire response under 2000 characters total. Short and actionable. Write like a lawyer advising a client — direct, clear, no fluff."""

    return prompt
