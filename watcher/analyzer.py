"""
AI Lead Analyzer & Point-of-Contact (POC) Extractor for SETS (www.sets4us.com).
Uses Google Gemini API (when configured) combined with a deterministic NLP + Regex
extraction engine for Energy Audit, Sustainability Audit, BMS, CMS, and ESG leads.
"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

from watcher.config import COMPANY_PROFILE

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)(?:971|966|91|44|1)[\s\-]?\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|\b05[02345689][\s\-]?\d{3}[\s\-]?\d{4}\b"
    r"|\b[6-9]\d{4}[\s\-]?\d{5}\b)"
)
LINKEDIN_REGEX = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|posts|company)/[^\s\"'<>]+")

NAME_PATTERNS = [
    re.compile(
        r"(?:contact|reach out to|email|attention|attn|posted by|from)\s+"
        r"((?:Eng\.|Dr\.|Mr\.|Ms\.|Mrs\.)?\s*[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){1,2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"((?:Eng\.|Dr\.)\s+[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){1,2})"
    ),
]

ROLE_COMPANY_PATTERNS = [
    # e.g. "(Head of Facilities Management, Gulf Horizon Properties)"
    re.compile(r"\(([^(),]{3,45}),\s*([^(),]{3,55})\)"),
    # e.g. "Sustainability Lead at Najd Industrial Holdings"
    re.compile(
        r",\s*([A-Za-z &/]{4,40}?)\s+at\s+([A-Z][A-Za-z0-9 &.\-]{2,45}?)(?=\s+(?:via|at|on|or|in)\b|[.,;]|$)"
    ),
]

NEGATIVE_SIGNALS = [
    "i am looking for a job",
    "open to work",
    "#opentowork",
    "my resume",
    "curriculum vitae",
    "fresh graduate looking",
]


def detect_region(text: str, active_regions: List[str]) -> str:
    text_lower = text.lower()
    scores = {r: 0 for r in COMPANY_PROFILE["regions"]}
    for region_code, rinfo in COMPANY_PROFILE["regions"].items():
        for loc in rinfo["locations"]:
            if re.search(r"\b" + re.escape(loc.lower()) + r"\b", text_lower):
                scores[region_code] += 2
        for prefix in rinfo["phone_prefixes"]:
            if prefix in text:
                scores[region_code] += 3

    best_region = max(scores, key=scores.get)
    if scores[best_region] > 0:
        return best_region
    return active_regions[0] if active_regions else "UAE"


def extract_poc_regex(text: str, url: str = "") -> Dict[str, str]:
    emails = EMAIL_REGEX.findall(text)
    phones = PHONE_REGEX.findall(text)
    linkedin_urls = LINKEDIN_REGEX.findall(text)
    if not linkedin_urls and "linkedin.com" in (url or "").lower():
        linkedin_urls = [url]

    poc_name = ""
    for pat in NAME_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip(" .,-")
            if len(candidate.split()) >= 2:
                poc_name = candidate
                break

    # If URL is a LinkedIn post/profile slug, infer name if still blank
    if not poc_name and "linkedin.com/" in (url or "").lower():
        slug_match = re.search(r"linkedin\.com/(?:posts|in)/([a-zA-Z0-9\-]+)", url)
        if slug_match:
            slug_parts = slug_match.group(1).split("_")[0].split("-")
            alpha_parts = [p.capitalize() for p in slug_parts if p.isalpha() and len(p) > 2][:2]
            if len(alpha_parts) >= 2:
                poc_name = " ".join(alpha_parts)

    poc_role = ""
    poc_company = ""
    for pat in ROLE_COMPANY_PATTERNS:
        m = pat.search(text)
        if m:
            poc_role = m.group(1).strip(" .,-")
            poc_company = m.group(2).strip(" .,-")
            break

    if not poc_company and emails:
        domain = emails[0].split("@")[-1].split(".")[0]
        if domain.lower() not in {"gmail", "yahoo", "outlook", "hotmail", "icloud"}:
            poc_company = domain.replace("-", " ").title()

    return {
        "poc_name": poc_name,
        "poc_role": poc_role,
        "poc_company": poc_company,
        "poc_email": emails[0] if emails else "",
        "poc_phone": phones[0].strip() if phones else "",
        "poc_linkedin": linkedin_urls[0] if linkedin_urls else "",
    }


def heuristic_analyze(
    item: Dict[str, Any], settings: Dict[str, Any]
) -> Dict[str, Any]:
    title = (item.get("title") or "").strip()
    snippet = (item.get("snippet") or "").strip()
    url = (item.get("url") or "").strip()
    source_platform = item.get("source_platform") or "Web"
    combined = f"{title}\n{snippet}"
    combined_lower = combined.lower()

    # Match SETS service categories
    service_scores: Dict[str, int] = {}
    matched_keywords: List[str] = []

    for cat_name, cat_info in COMPANY_PROFILE["services"].items():
        score = 0
        for kw in cat_info["keywords"]:
            if kw.lower() in combined_lower:
                score += 18
                matched_keywords.append(kw)
        # Also check category name itself
        if cat_name.lower() in combined_lower:
            score += 20
        if score > 0:
            service_scores[cat_name] = score

    # Check user custom keywords
    custom_kws = [
        k.strip()
        for k in (settings.get("custom_keywords") or "").split(",")
        if k.strip()
    ]
    for ckw in custom_kws:
        if ckw.lower() in combined_lower:
            service_scores["Energy Audit"] = service_scores.get("Energy Audit", 0) + 12

    if service_scores:
        sorted_cats = sorted(service_scores.keys(), key=lambda c: service_scores[c], reverse=True)
        primary_category = sorted_cats[0]
        matched_services = sorted_cats[:3]
        base_score = min(55, service_scores[primary_category] + 25)
    else:
        primary_category = item.get("default_category") or "Energy Audit"
        matched_services = [primary_category]
        base_score = 30

    # Intent signal boost
    intent_hits = []
    for sig in COMPANY_PROFILE["intent_signals"]:
        if re.search(r"\b" + re.escape(sig.lower()) + r"\b", combined_lower):
            intent_hits.append(sig)
            base_score += 10

    # Negative signal penalty (job seekers)
    is_genuine = True
    for neg in NEGATIVE_SIGNALS:
        if neg in combined_lower:
            base_score -= 35
            is_genuine = False

    poc = extract_poc_regex(combined, url)
    if poc["poc_email"]:
        base_score += 12
    if poc["poc_phone"]:
        base_score += 12
    if poc["poc_name"] or poc["poc_company"]:
        base_score += 6

    relevance_score = max(10, min(98, base_score))
    if relevance_score < 45:
        is_genuine = False

    urgency = "High" if relevance_score >= 80 else ("Medium" if relevance_score >= 60 else "Low")
    region = item.get("region") or detect_region(combined, settings.get("active_regions", ["UAE", "KSA", "India"]))

    # Find specific city if present
    poc_location = region
    for loc in COMPANY_PROFILE["regions"].get(region, {}).get("locations", []):
        if re.search(r"\b" + re.escape(loc.lower()) + r"\b", combined_lower):
            if loc.upper() != region.upper():
                poc_location = f"{loc}, {region}"
                break

    services_str = " & ".join(matched_services)
    greeting = f"Dear {poc['poc_name']}," if poc["poc_name"] else "Hello Team,"
    company_ref = f" for {poc['poc_company']}" if poc["poc_company"] else ""

    ai_summary = (
        f"Detected {urgency.lower()}-priority {services_str} opportunity in {poc_location}"
        f"{company_ref}. "
        + (
            f"Intent indicators matched: {', '.join(intent_hits[:4])}."
            if intent_hits
            else "Matches SETS core engineering & sustainability portfolio."
        )
    )

    suggested_pitch = (
        f"{greeting} We noticed your requirement regarding {services_str}{company_ref} in {poc_location}. "
        f"SETS (www.sets4us.com) is a specialized engineering consultancy delivering ASHRAE Energy Audits, "
        f"Sustainability Audits, BMS/CMS Engineering, and ESG Reporting across UAE, KSA, and India. "
        f"We would be pleased to share our technical credentials and discuss your scope of work."
    )

    return {
        "title": title or "New Enquiry Detected",
        "snippet": snippet,
        "url": url,
        "source_platform": source_platform,
        "category": primary_category,
        "matched_services": matched_services,
        "region": region,
        "relevance_score": relevance_score,
        "urgency": urgency,
        "is_genuine_enquiry": is_genuine,
        "ai_summary": ai_summary,
        "poc_name": poc["poc_name"],
        "poc_role": poc["poc_role"],
        "poc_company": poc["poc_company"],
        "poc_email": poc["poc_email"],
        "poc_phone": poc["poc_phone"],
        "poc_linkedin": poc["poc_linkedin"],
        "poc_location": poc_location,
        "suggested_pitch": suggested_pitch,
        "analyzed_by": "Hybrid NLP Engine",
        "published_at": item.get("published_at", ""),
    }


def gemini_analyze(
    item: Dict[str, Any], settings: Dict[str, Any], fallback_result: Dict[str, Any]
) -> Dict[str, Any]:
    api_key = (settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return fallback_result

    model = (settings.get("gemini_model") or "gemini-2.5-flash").strip()
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    )

    prompt = f"""You are an AI Lead Intelligence Analyst for SETS (www.sets4us.com), an engineering & sustainability firm operating in UAE, KSA (Saudi Arabia), and India.
SETS core activities:
1. Energy Audit (ASHRAE Level 1/2/3, ISO 50001, ESCO, HVAC/Chiller/Industrial Energy Audits, Retro-commissioning)
2. Sustainability Audit (Green Building LEED, Estidama, Mostadam, Al Sa'fat, IGBC, Net Zero, Decarbonization)
3. BMS (Building Management Systems, HVAC Controls, BACnet, Niagara, BMS Retrofit/AMC)
4. CMS (Central Monitoring Systems, EMS, IoT Smart Metering, Command Centers, Fault Detection)
5. ESG Reporting (GRI, Tadawul ESG, ADX/DFM ESG, SEBI BRSR, Scope 1/2/3 GHG Inventory, Carbon Accounting)

Analyze the following internet/social post and return a strict JSON object with these keys:
- "is_genuine_enquiry": boolean (true if this is a business enquiry, RFP, RFQ, tender, vendor search, project opportunity, or consultancy requirement; false if job seeker CV or unrelated)
- "category": one of ["Energy Audit", "Sustainability Audit", "BMS", "CMS", "ESG Reporting"]
- "matched_services": array of matching service names from the 5 above
- "region": one of ["UAE", "KSA", "India", "Global"]
- "relevance_score": integer 0-100 indicating fit & commercial intent for www.sets4us.com
- "urgency": one of ["High", "Medium", "Low"]
- "ai_summary": concise 1-2 sentence executive summary of the requirement
- "poc_name": contact person's name if mentioned (or "")
- "poc_role": contact person's job title/role if mentioned (or "")
- "poc_company": organization or company issuing the enquiry (or "")
- "poc_email": email address if mentioned (or "")
- "poc_phone": phone/WhatsApp number if mentioned (or "")
- "poc_location": city & country if identifiable (e.g. "Dubai, UAE")
- "suggested_pitch": short, tailored outreach message from SETS (www.sets4us.com) to the contact person

Post Title: {item.get("title", "")}
Post Content: {item.get("snippet", "")}
Source URL: {item.get("url", "")}
Platform: {item.get("source_platform", "")}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        candidates = body.get("candidates", [])
        if not candidates:
            return fallback_result
        text_out = candidates[0]["content"]["parts"][0]["text"]
        parsed = json.loads(text_out)

        merged = dict(fallback_result)
        merged["is_genuine_enquiry"] = bool(parsed.get("is_genuine_enquiry", merged["is_genuine_enquiry"]))
        if parsed.get("category") in COMPANY_PROFILE["services"]:
            merged["category"] = parsed["category"]
        if isinstance(parsed.get("matched_services"), list) and parsed["matched_services"]:
            merged["matched_services"] = parsed["matched_services"]
        if parsed.get("region"):
            merged["region"] = parsed["region"]
        if parsed.get("relevance_score") is not None:
            merged["relevance_score"] = max(0, min(100, int(parsed["relevance_score"])))
        if parsed.get("urgency") in ("High", "Medium", "Low"):
            merged["urgency"] = parsed["urgency"]
        if parsed.get("ai_summary"):
            merged["ai_summary"] = parsed["ai_summary"]
        for field in ("poc_name", "poc_role", "poc_company", "poc_email", "poc_phone", "poc_location", "suggested_pitch"):
            if parsed.get(field):
                merged[field] = str(parsed[field]).strip()
        merged["analyzed_by"] = f"Google Gemini ({model})"
        return merged
    except Exception:
        return fallback_result


def analyze_item(item: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    """Run hybrid NLP + regex first, then enrich with Google Gemini if configured and promising."""
    base = heuristic_analyze(item, settings)
    # Call Gemini if API key is configured and item has at least minimal topical signal
    if base["relevance_score"] >= 35 or item.get("force_ai"):
        return gemini_analyze(item, settings, base)
    return base

