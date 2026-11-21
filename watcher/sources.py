"""
Multi-Source Internet & LinkedIn Discovery Engine for SETS (www.sets4us.com).

Design notes (verified against the live endpoints, Nov 2026):
- Google News RSS is the most reliable open source. It answers natural-language
  queries well but returns nothing for jargon-heavy boolean queries, so every
  query is sent as a "fallback ladder": specific -> broader -> broadest.
- Bing News RSS works for natural queries. Bing *web* RSS ignores the query and
  returns unrelated pages, so it is not used.
- DuckDuckGo HTML and Reddit JSON frequently answer automated clients with a
  bot-challenge / HTTP 403. Those responses are detected, reported in the
  Source Health panel, and the source is paused for a cool-down period instead
  of being hammered on every query.
- Every result passes a relevance gate (on-topic term + in-region term, junk
  domains removed) and carries its publisher website so the app can list the
  informative websites it discovers.
"""

import html
import json
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

TAG_STRIP_RE = re.compile(r"<[^>]+>")

# Rotating cursor so consecutive scans always query fresh combinations
_ROTATING_CURSOR = 0

# ---------------------------------------------------------------------------
# Source health tracking & cool-down for sources that block automated clients
# ---------------------------------------------------------------------------

SOURCE_LABELS = {
    "google_news_rss": ("Google News RSS", "https://news.google.com/"),
    "bing_news_rss": ("Bing News RSS", "https://www.bing.com/news"),
    "linkedin_social": ("LinkedIn Public Job/Company Search", "https://www.linkedin.com/jobs/"),
    "duckduckgo_web": ("DuckDuckGo Web Search", "https://duckduckgo.com/"),
    "reddit_communities": ("Reddit Communities", "https://www.reddit.com/"),
    "google_cse": ("Google Custom Search API", "https://programmablesearchengine.google.com/"),
    "serpapi": ("SerpAPI Google Search", "https://serpapi.com/"),
    "custom_rss": ("Custom RSS Feeds", ""),
}

BLOCK_COOLDOWN_SECONDS = 30 * 60

_health_lock = threading.Lock()
SOURCE_HEALTH: Dict[str, Dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record_health(source: str, status: str, items: int = 0, detail: str = "") -> None:
    """status: ok | empty | blocked | error"""
    with _health_lock:
        h = SOURCE_HEALTH.setdefault(
            source,
            {"requests": 0, "items": 0, "blocked_until": 0.0},
        )
        h["requests"] += 1
        h["items"] += items
        h["last_status"] = status
        h["last_detail"] = detail[:240]
        h["last_checked"] = _utc_now_iso()
        if status == "blocked":
            h["blocked_until"] = time.time() + BLOCK_COOLDOWN_SECONDS


def _is_paused(source: str) -> bool:
    with _health_lock:
        h = SOURCE_HEALTH.get(source)
        return bool(h and h.get("blocked_until", 0) > time.time())


def get_source_health() -> List[Dict[str, Any]]:
    """Snapshot of accumulated per-source statistics since the app started."""
    out: List[Dict[str, Any]] = []
    with _health_lock:
        for key, (label, home) in SOURCE_LABELS.items():
            h = SOURCE_HEALTH.get(key)
            if not h:
                continue
            paused_for = max(0, int(h.get("blocked_until", 0) - time.time()))
            out.append(
                {
                    "source": key,
                    "label": label,
                    "homepage": home,
                    "requests": h["requests"],
                    "items": h["items"],
                    "last_status": h.get("last_status", ""),
                    "last_detail": h.get("last_detail", ""),
                    "last_checked": h.get("last_checked", ""),
                    "paused_minutes": round(paused_for / 60),
                }
            )
    return out


# ---------------------------------------------------------------------------
# Relevance gate
# ---------------------------------------------------------------------------

JUNK_DOMAINS = (
    "wikipedia.org",
    "wiktionary.org",
    "merriam-webster.com",
    "dictionary.com",
    "britannica.com",
    "collinsdictionary.com",
    "cambridge.org",
    "thesaurus.com",
    "youtube.com",
    "pinterest.",
)

# Domain terms: at least one must appear in the headline/summary. Generic business
# words (tender, contract, project, consultant) are deliberately NOT enough on their
# own, otherwise unrelated tenders (e.g. social-media agency contracts) slip through.
TOPIC_TERMS = (
    "energy", "energy audit", "sustainab", "green building", "leed", "estidama", "mostadam",
    "igbc", "griha", "net zero", "net-zero", "carbon", "decarbon", "emission", "esg",
    "brsr", "ghg", "climate", "building management", "bms", "building automation", "hvac",
    "chiller", "cooling", "smart building", "smart city", "iot", "energy monitoring",
    "monitoring system", "scada", "metering", "smart meter", "facility management",
    "facilities management", "mep", "retrofit", "efficien", "esco", "solar", "renewable",
    "electricity", "utilities", "construction", "data center", "data centre", "hospital",
    "tower", "skyscraper", "factory", "factories", "warehouse", "industrial", "real estate",
    "building", "buildings", "command centre", "command center", "infrastructure",
)
_TOPIC_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in TOPIC_TERMS) + r")", re.IGNORECASE)

REGION_TERMS = {
    "UAE": (
        "uae", "u.a.e", "emirates", "dubai", "abu dhabi", "sharjah", "ajman",
        "ras al khaimah", "rak ", "fujairah", "umm al quwain", "dewa", "addc", "sewa",
        "etihad esco", "adnoc", "emaar", "aldar", "masdar", "kezad", "jafza", "dubai south",
    ),
    "KSA": (
        "saudi", "ksa", "riyadh", "jeddah", "dammam", "khobar", "neom", "red sea global",
        "qiddiya", "aramco", "sabic", "makkah", "mecca", "madinah", "medina", "tabuk",
        "jubail", "yanbu", "vision 2030", "roshn", "diriyah",
    ),
    "India": (
        "india", "mumbai", "delhi", "ncr", "noida", "gurugram", "gurgaon", "bengaluru",
        "bangalore", "chennai", "hyderabad", "pune", "ahmedabad", "kolkata", "kochi",
        "kerala", "karnataka", "maharashtra", "tamil nadu", "telangana", "gujarat",
        "gift city", "sebi", "rupee", "crore", "lakh", "inr",
    ),
}

_REGION_RE = {
    reg: re.compile(r"\b(?:" + "|".join(re.escape(t.strip()) for t in terms) + r")\b", re.IGNORECASE)
    for reg, terms in REGION_TERMS.items()
}


def mentions_region(text: str, region: str) -> bool:
    rx = _REGION_RE.get(region)
    return bool(rx and rx.search(text))


def _domain_of(url: str) -> str:
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def is_relevant(item: Dict[str, Any], region: str, require_region: bool = True) -> bool:
    url = item.get("url", "")
    site = item.get("publisher_site") or url
    dom = _domain_of(site)
    if any(j in dom for j in JUNK_DOMAINS) or any(j in _domain_of(url) for j in JUNK_DOMAINS):
        return False
    # Judge only the headline + summary, not the appended "Source website: ..." metadata
    snippet = (item.get("snippet", "") or "").split(" | Source website:")[0]
    text = f" {item.get('title', '')} {snippet} "
    if not _TOPIC_RE.search(text):
        return False
    if require_region and region in REGION_TERMS and not mentions_region(text, region):
        return False
    return True


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

REGION_CITIES = {
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah", "UAE", "Ras Al Khaimah", "Ajman"],
    "KSA": ["Riyadh", "Saudi Arabia", "Jeddah", "Dammam", "NEOM", "Khobar"],
    "India": ["Mumbai", "Bengaluru", "India", "Chennai", "Hyderabad", "Delhi", "Pune", "Kochi", "Ahmedabad"],
}

# Plain-language phrases: these are what news headlines actually contain.
CATEGORY_PHRASES = {
    "Energy Audit": [
        "energy audit",
        "energy efficiency retrofit",
        "energy performance contract ESCO",
        "energy savings building",
        "ISO 50001 energy management",
    ],
    "Sustainability Audit": [
        "sustainability consultant",
        "green building certification",
        "LEED certified building",
        "net zero building",
        "decarbonisation strategy",
    ],
    "BMS": [
        "building management system",
        "smart building automation",
        "HVAC upgrade contract",
        "district cooling chiller plant",
        "MEP contract awarded",
    ],
    "CMS": [
        "central monitoring system",
        "energy management system",
        "smart metering",
        "IoT building monitoring",
        "command and control centre",
    ],
    "ESG Reporting": [
        "ESG reporting",
        "sustainability report",
        "carbon footprint emissions disclosure",
        "ESG consultant",
        "climate disclosure",
    ],
}

REGION_SPECIFIC_PHRASES = {
    ("UAE", "Sustainability Audit"): ["Estidama Pearl rating", "Al Sa'fat green building"],
    ("KSA", "Sustainability Audit"): ["Mostadam rating", "Saudi Green Initiative building"],
    ("India", "Sustainability Audit"): ["IGBC green building", "GRIHA rating"],
    ("India", "ESG Reporting"): ["BRSR reporting"],
    ("KSA", "Energy Audit"): ["Tarshid energy efficiency"],
    ("UAE", "Energy Audit"): ["Etihad ESCO retrofit"],
}

INTENT_SUFFIXES = ["tender", "contract", "project", ""]


def clean_html_text(raw: str) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    stripped = TAG_STRIP_RE.sub(" ", unescaped)
    return " ".join(stripped.split())


def _ladder(phrase: str, city: str, suffix: str) -> List[str]:
    """Specific -> broader -> broadest query variants for one topic."""
    specific = f"{phrase} {suffix} {city}".replace("  ", " ").strip()
    broad = f"{phrase} {city}".strip()
    ladder = [f"{specific} when:30d", f"{broad} when:90d", broad]
    seen: List[str] = []
    for q in ladder:
        if q not in seen:
            seen.append(q)
    return seen


def build_discovery_queries(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    regions = settings.get("active_regions") or ["UAE", "KSA", "India"]
    categories = settings.get("active_categories") or list(CATEGORY_PHRASES.keys())

    queries: List[Dict[str, Any]] = []
    for reg in regions:
        cities = REGION_CITIES.get(reg, [reg])
        for cat in categories:
            phrases = list(CATEGORY_PHRASES.get(cat, [cat]))
            phrases = REGION_SPECIFIC_PHRASES.get((reg, cat), []) + phrases
            for idx, phrase in enumerate(phrases):
                city = cities[idx % len(cities)]
                suffix = INTENT_SUFFIXES[idx % len(INTENT_SUFFIXES)]
                queries.append(
                    {
                        "region": reg,
                        "category": cat,
                        "city": city,
                        "phrase": phrase,
                        "news_ladder": _ladder(phrase, city, suffix),
                        "linkedin_keyword": phrase,
                        "web_query": f"{phrase} {suffix} {city}".strip(),
                    }
                )

    custom_kws = [k.strip() for k in (settings.get("custom_keywords") or "").split(",") if k.strip()]
    for ckw in custom_kws[:8]:
        for reg in regions:
            city = REGION_CITIES.get(reg, [reg])[0]
            queries.append(
                {
                    "region": reg,
                    "category": "Energy Audit",
                    "city": city,
                    "phrase": ckw,
                    "news_ladder": _ladder(ckw, reg if reg != "KSA" else "Saudi Arabia", ""),
                    "linkedin_keyword": ckw,
                    "web_query": f"{ckw} {reg}",
                }
            )

    # Interleave regions/categories so a 10-query slice is always diverse
    random.Random(42).shuffle(queries)
    return queries


# ---------------------------------------------------------------------------
# HTTP + parsing helpers
# ---------------------------------------------------------------------------

def fetch_url(url: str, timeout: int = 10, extra_headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _unwrap_bing_link(link: str) -> str:
    if "bing.com/news/apiclick" in link.lower():
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        if qs.get("url"):
            return qs["url"][0]
    return link


def parse_rss_xml(xml_bytes: bytes, source_platform: str, region: str, category: str, limit: int = 12) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return items
    for item_el in root.findall(".//item")[:limit]:
        title = clean_html_text(item_el.findtext("title") or "")
        link = _unwrap_bing_link((item_el.findtext("link") or "").strip())
        desc = clean_html_text(item_el.findtext("description") or "")
        pub_date = (item_el.findtext("pubDate") or "").strip()
        if not title or not link:
            continue

        publisher = ""
        publisher_site = ""
        for child in list(item_el):
            tag = child.tag.split("}")[-1].lower()
            if tag == "source":
                publisher = clean_html_text(child.text or "")
                publisher_site = (child.attrib.get("url") or "").strip()
        if not publisher_site and "news.google.com" not in link:
            dom = _domain_of(link)
            publisher_site = f"https://{dom}" if dom else ""
        if not publisher and publisher_site:
            publisher = _domain_of(publisher_site)

        # Google News titles end with " - Publisher"; keep the headline clean
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].strip()
        # Google News descriptions repeat the headline; only keep if it adds info
        if desc and (desc.startswith(title) or len(desc) < 20):
            desc = ""

        platform_label = "LinkedIn" if "linkedin.com" in link.lower() else source_platform
        snippet_parts = [desc or title]
        if publisher:
            snippet_parts.append(f"Source website: {publisher}" + (f" ({publisher_site})" if publisher_site else ""))
        if pub_date:
            snippet_parts.append(f"Published: {pub_date}")
        items.append(
            {
                "title": title,
                "snippet": " | ".join(snippet_parts),
                "url": link,
                "source_platform": platform_label,
                "region": region,
                "default_category": category,
                "published_at": pub_date,
                "publisher": publisher,
                "publisher_site": publisher_site,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Individual sources
# ---------------------------------------------------------------------------

GL_MAP = {
    "UAE": ("AE", "en-AE", "AE:en"),
    "KSA": ("SA", "en-SA", "SA:en"),
    "India": ("IN", "en-IN", "IN:en"),
}


def search_google_news_rss(query_str: str, region: str, category: str, platform_label: str = "Web / Tenders") -> List[Dict[str, Any]]:
    gl, hl, ceid = GL_MAP.get(region, ("US", "en-US", "US:en"))
    q = urllib.parse.quote_plus(query_str)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        raw = fetch_url(url, timeout=10)
        items = parse_rss_xml(raw, platform_label, region, category)
        _record_health("google_news_rss", "ok" if items else "empty", len(items), query_str)
        return items
    except urllib.error.HTTPError as exc:
        _record_health("google_news_rss", "blocked" if exc.code in (403, 429) else "error", 0, f"HTTP {exc.code}")
    except Exception as exc:
        _record_health("google_news_rss", "error", 0, str(exc))
    return []


def search_google_news_ladder(ladder: List[str], region: str, category: str) -> List[Dict[str, Any]]:
    """Try the specific query first and broaden until something relevant comes back."""
    if _is_paused("google_news_rss"):
        return []
    for q in ladder:
        relevant = [i for i in search_google_news_rss(q, region, category) if is_relevant(i, region)]
        if relevant:
            return relevant
    return []


def search_bing_news_rss(query_str: str, region: str, category: str, platform_label: str = "Web / Tenders") -> List[Dict[str, Any]]:
    if _is_paused("bing_news_rss"):
        return []
    clean_q = re.sub(r"\bwhen:\d+[dhy]\b", "", query_str).strip()
    q = urllib.parse.quote_plus(clean_q)
    url = f"https://www.bing.com/news/search?q={q}&format=rss"
    try:
        raw = fetch_url(url, timeout=10)
        items = parse_rss_xml(raw, platform_label, region, category)
        _record_health("bing_news_rss", "ok" if items else "empty", len(items), clean_q)
        return [i for i in items if is_relevant(i, region)]
    except urllib.error.HTTPError as exc:
        _record_health("bing_news_rss", "blocked" if exc.code in (403, 429) else "error", 0, f"HTTP {exc.code}")
    except Exception as exc:
        _record_health("bing_news_rss", "error", 0, str(exc))
    return []


# Kept for backward compatibility with older callers
def search_bing_rss(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    return search_bing_news_rss(query_str, region, category, platform_label)


def search_linkedin_direct_guest(
    keyword: str, location: str, region: str, category: str, settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    LinkedIn's public guest job-search endpoint. Results are *job postings*; they are
    labelled as such and treated as a market signal (the organisation is actively
    staffing energy / sustainability / BMS work), not as a direct enquiry.
    """
    if _is_paused("linkedin_social"):
        return []
    items: List[Dict[str, Any]] = []
    q = urllib.parse.quote_plus(keyword)
    loc = urllib.parse.quote_plus(location)
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={q}&location={loc}&f_TPR=r2592000&start=0"
    )
    extra_headers: Dict[str, str] = {}
    li_at = (settings.get("linkedin_li_at_cookie") or "").strip()
    if li_at:
        extra_headers["Cookie"] = f"li_at={li_at}"

    try:
        raw = fetch_url(url, timeout=10, extra_headers=extra_headers).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        _record_health("linkedin_social", "blocked" if exc.code in (403, 429, 999) else "error", 0, f"HTTP {exc.code}")
        return items
    except Exception as exc:
        _record_health("linkedin_social", "error", 0, str(exc))
        return items

    card_blocks = re.findall(r"<li[^>]*>(.*?)</li>", raw, re.DOTALL | re.IGNORECASE)
    for block in card_blocks[:6]:
        title_m = re.search(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h', block, re.DOTALL | re.IGNORECASE)
        comp_m = re.search(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</h', block, re.DOTALL | re.IGNORECASE)
        loc_m = re.search(r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span', block, re.DOTALL | re.IGNORECASE)
        date_m = re.search(r'<time[^>]*datetime="([^"]+)"', block, re.IGNORECASE)
        href_m = re.search(r'href="(https://[^"]*linkedin\.com/[^"]+)"', block, re.IGNORECASE)
        if not title_m or not href_m:
            continue
        role_title = clean_html_text(title_m.group(1))
        company = clean_html_text(comp_m.group(1)) if comp_m else "Organisation on LinkedIn"
        loc_text = clean_html_text(loc_m.group(1)) if loc_m else location
        link = href_m.group(1).split("?")[0]
        items.append(
            {
                "title": f"[LinkedIn Job Posting] {role_title} — {company} ({loc_text})",
                "snippet": (
                    f"{company} is hiring for '{role_title}' in {loc_text}. Market signal: this organisation "
                    f"has active {category} / engineering & sustainability work in the region — a potential "
                    f"client or partner for consultancy services. Source website: LinkedIn (https://www.linkedin.com)"
                ),
                "url": link,
                "source_platform": "LinkedIn",
                "region": region,
                "default_category": category,
                "published_at": date_m.group(1) if date_m else "",
                "publisher": "LinkedIn",
                "publisher_site": "https://www.linkedin.com",
                "poc_company_hint": company,
            }
        )
    _record_health("linkedin_social", "ok" if items else "empty", len(items), f"{keyword} @ {location}")
    return items


def search_duckduckgo_html(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    if _is_paused("duckduckgo_web"):
        return []
    q = urllib.parse.quote_plus(re.sub(r"\bwhen:\d+[dhy]\b", "", query_str).strip())
    url = f"https://html.duckduckgo.com/html/?q={q}"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=10).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        _record_health("duckduckgo_web", "blocked" if exc.code in (202, 403, 429) else "error", 0, f"HTTP {exc.code}")
        return items
    except Exception as exc:
        _record_health("duckduckgo_web", "error", 0, str(exc))
        return items

    if "anomaly" in raw.lower() and "result__a" not in raw:
        _record_health("duckduckgo_web", "blocked", 0, "Bot-challenge page returned (automated access refused)")
        return items

    link_pattern = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
    snippet_pattern = re.compile(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
    links = link_pattern.findall(raw)
    snippets = snippet_pattern.findall(raw)
    for idx, (href, raw_title) in enumerate(links[:8]):
        actual_url = href
        if "uddg=" in href:
            parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if "uddg" in parsed_qs:
                actual_url = parsed_qs["uddg"][0]
        title = clean_html_text(raw_title)
        snippet = clean_html_text(snippets[idx]) if idx < len(snippets) else title
        if not title or not actual_url.startswith("http"):
            continue
        dom = _domain_of(actual_url)
        item = {
            "title": title,
            "snippet": f"{snippet} | Source website: {dom} (https://{dom})",
            "url": actual_url,
            "source_platform": "LinkedIn" if "linkedin.com" in actual_url.lower() else platform_label,
            "region": region,
            "default_category": category,
            "published_at": "",
            "publisher": dom,
            "publisher_site": f"https://{dom}",
        }
        if is_relevant(item, region):
            items.append(item)
    _record_health("duckduckgo_web", "ok" if items else "empty", len(items), query_str)
    return items


def search_reddit_json(query_str: str, region: str, category: str) -> List[Dict[str, Any]]:
    if _is_paused("reddit_communities"):
        return []
    q = urllib.parse.quote_plus(query_str)
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&t=month&limit=8"
    items: List[Dict[str, Any]] = []
    try:
        data = json.loads(fetch_url(url, timeout=9).decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as exc:
        _record_health("reddit_communities", "blocked" if exc.code in (403, 429) else "error", 0, f"HTTP {exc.code} (Reddit refuses anonymous API clients)")
        return items
    except Exception as exc:
        _record_health("reddit_communities", "error", 0, str(exc))
        return items
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = clean_html_text(post.get("title") or "")
        permalink = post.get("permalink") or ""
        if not title or not permalink:
            continue
        item = {
            "title": title,
            "snippet": f"[{post.get('subreddit_name_prefixed') or 'Reddit'}] {clean_html_text(post.get('selftext') or title)[:1400]}",
            "url": f"https://www.reddit.com{permalink}",
            "source_platform": "Reddit / Social",
            "region": region,
            "default_category": category,
            "published_at": "",
            "publisher": "Reddit",
            "publisher_site": "https://www.reddit.com",
        }
        if is_relevant(item, region):
            items.append(item)
    _record_health("reddit_communities", "ok" if items else "empty", len(items), query_str)
    return items


def _api_results_to_items(entries: List[Dict[str, Any]], link_key: str, label: str, region: str, category: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in entries:
        link = entry.get(link_key, "")
        if not link:
            continue
        dom = _domain_of(link)
        item = {
            "title": clean_html_text(entry.get("title", "")),
            "snippet": f"{clean_html_text(entry.get('snippet', ''))} | Source website: {dom} (https://{dom})",
            "url": link,
            "source_platform": "LinkedIn" if "linkedin.com" in link.lower() else label,
            "region": region,
            "default_category": category,
            "published_at": "",
            "publisher": dom,
            "publisher_site": f"https://{dom}",
        }
        if is_relevant(item, region):
            out.append(item)
    return out


def search_google_cse(query_str: str, region: str, category: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    api_key = (settings.get("google_cse_api_key") or "").strip()
    cx = (settings.get("google_cse_cx_id") or settings.get("google_cse_cx") or "").strip()
    if not api_key or not cx:
        return []
    q = urllib.parse.quote_plus(query_str)
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={q}&num=8"
    try:
        data = json.loads(fetch_url(url, timeout=10).decode("utf-8", errors="ignore"))
        items = _api_results_to_items(data.get("items", []), "link", "Google Search", region, category)
        _record_health("google_cse", "ok" if items else "empty", len(items), query_str)
        return items
    except urllib.error.HTTPError as exc:
        _record_health("google_cse", "error", 0, f"HTTP {exc.code} (check API key / quota)")
    except Exception as exc:
        _record_health("google_cse", "error", 0, str(exc))
    return []


def search_serpapi(query_str: str, region: str, category: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    api_key = (settings.get("serpapi_key") or "").strip()
    if not api_key:
        return []
    q = urllib.parse.quote_plus(query_str)
    url = f"https://serpapi.com/search.json?engine=google&q={q}&api_key={api_key}&num=8"
    try:
        data = json.loads(fetch_url(url, timeout=10).decode("utf-8", errors="ignore"))
        items = _api_results_to_items(data.get("organic_results", []), "link", "SerpAPI Web", region, category)
        _record_health("serpapi", "ok" if items else "empty", len(items), query_str)
        return items
    except urllib.error.HTTPError as exc:
        _record_health("serpapi", "error", 0, f"HTTP {exc.code} (check API key / quota)")
    except Exception as exc:
        _record_health("serpapi", "error", 0, str(exc))
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (it.get("url") or "").split("?")[0].lower() or it.get("title", "").lower()
        tkey = re.sub(r"\W+", " ", it.get("title", "").lower()).strip()
        if key in seen or tkey in seen:
            continue
        seen.add(key)
        seen.add(tkey)
        out.append(it)
    return out


def run_multi_source_discovery(
    settings: Dict[str, Any], max_queries: int = 10
) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Execute discovery across enabled sources using a rotating query cursor so
    consecutive scans cover new keywords, cities, and platforms.
    """
    global _ROTATING_CURSOR
    active_sources = set(settings.get("active_sources") or [])
    all_queries = build_discovery_queries(settings)
    if not all_queries:
        return [], 0, []

    total_q = len(all_queries)
    selected = [all_queries[(_ROTATING_CURSOR + i) % total_q] for i in range(min(max_queries, total_q))]
    _ROTATING_CURSOR = (_ROTATING_CURSOR + max_queries) % total_q

    discovered: List[Dict[str, Any]] = []
    queries_executed = 0
    errors: List[str] = []

    for qinfo in selected:
        reg, cat, city = qinfo["region"], qinfo["category"], qinfo["city"]

        if "google_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(search_google_news_ladder(qinfo["news_ladder"], reg, cat))

        if "bing_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(search_bing_news_rss(qinfo["web_query"], reg, cat))

        if "linkedin_social" in active_sources:
            queries_executed += 1
            discovered.extend(search_linkedin_direct_guest(qinfo["linkedin_keyword"], city, reg, cat, settings))

        if "duckduckgo_web" in active_sources and not _is_paused("duckduckgo_web"):
            queries_executed += 1
            discovered.extend(search_duckduckgo_html(qinfo["web_query"], "Web / Tenders", reg, cat))

        if "reddit_communities" in active_sources and not _is_paused("reddit_communities"):
            queries_executed += 1
            discovered.extend(search_reddit_json(f"{qinfo['phrase']} {city}", reg, cat))

        if settings.get("google_cse_api_key") and (settings.get("google_cse_cx_id") or settings.get("google_cse_cx")):
            queries_executed += 1
            discovered.extend(search_google_cse(qinfo["web_query"], reg, cat, settings))
        if settings.get("serpapi_key"):
            queries_executed += 1
            discovered.extend(search_serpapi(qinfo["web_query"], reg, cat, settings))

    custom_rss = (settings.get("custom_rss_urls") or "").strip()
    for rss_url in [u.strip() for u in custom_rss.splitlines() if u.strip().startswith("http")]:
        try:
            queries_executed += 1
            parsed = parse_rss_xml(fetch_url(rss_url, timeout=10), "Custom RSS", "UAE", "Energy Audit", limit=20)
            kept = []
            for it in parsed:
                for reg in settings.get("active_regions") or ["UAE", "KSA", "India"]:
                    if is_relevant(it, reg):
                        it["region"] = reg
                        kept.append(it)
                        break
            _record_health("custom_rss", "ok" if kept else "empty", len(kept), rss_url)
            discovered.extend(kept)
        except Exception as exc:
            _record_health("custom_rss", "error", 0, f"{rss_url}: {exc}")
            errors.append(f"Custom RSS ({rss_url}): {exc}")

    for h in get_source_health():
        if h["last_status"] == "blocked":
            errors.append(f"{h['label']} is refusing automated access ({h['last_detail']}); paused for {h['paused_minutes']} min.")

    discovered = _dedupe(discovered)
    random.shuffle(discovered)
    return discovered, queries_executed, errors


def run_custom_live_search(keyword: str, region: str, category: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """On-demand search for a user keyword across all open sources."""
    kw = keyword.strip()
    if not kw:
        return []
    regions = [region] if region and region != "ALL" else (settings.get("active_regions") or ["UAE", "KSA", "India"])
    cat = category if category and category != "ALL" else "Energy Audit"
    items: List[Dict[str, Any]] = []
    for reg in regions:
        place = "Saudi Arabia" if reg == "KSA" else reg
        kw_has_place = mentions_region(kw, reg)
        base = kw if kw_has_place else f"{kw} {place}"
        ladder = [f"{base} when:30d", f"{base} when:180d", base]
        items.extend(search_google_news_ladder(ladder, reg, cat))
        items.extend(search_bing_news_rss(base, reg, cat))
        items.extend(search_linkedin_direct_guest(kw, place, reg, cat, settings))
        items.extend(search_duckduckgo_html(base, "Web / Tenders", reg, cat))
        if settings.get("google_cse_api_key"):
            items.extend(search_google_cse(base, reg, cat, settings))
        if settings.get("serpapi_key"):
            items.extend(search_serpapi(base, reg, cat, settings))
    return _dedupe(items)


def probe_sources(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Live check of every source with one small query. Returns per-source status,
    result count, latency, and the websites the results came from.
    """
    checks = [
        ("google_news_rss", lambda: search_google_news_rss("building energy efficiency Dubai", "UAE", "Energy Audit")),
        ("bing_news_rss", lambda: search_bing_news_rss("Dubai building management system", "UAE", "BMS")),
        ("linkedin_social", lambda: search_linkedin_direct_guest("energy audit", "Dubai", "UAE", "Energy Audit", settings)),
        ("duckduckgo_web", lambda: search_duckduckgo_html("energy audit tender Dubai", "Web", "UAE", "Energy Audit")),
        ("reddit_communities", lambda: search_reddit_json("energy efficiency Dubai", "UAE", "Energy Audit")),
    ]
    if settings.get("google_cse_api_key"):
        checks.append(("google_cse", lambda: search_google_cse("energy audit tender Dubai", "UAE", "Energy Audit", settings)))
    if settings.get("serpapi_key"):
        checks.append(("serpapi", lambda: search_serpapi("energy audit tender Dubai", "UAE", "Energy Audit", settings)))

    results: List[Dict[str, Any]] = []
    for key, fn in checks:
        # A manual probe should always really test the source, even if paused
        with _health_lock:
            if key in SOURCE_HEALTH:
                SOURCE_HEALTH[key]["blocked_until"] = 0.0
        t0 = time.time()
        items = fn()
        latency = int((time.time() - t0) * 1000)
        with _health_lock:
            h = dict(SOURCE_HEALTH.get(key) or {})
        label, home = SOURCE_LABELS[key]
        sites = sorted({(i.get("publisher") or "", i.get("publisher_site") or "") for i in items if i.get("publisher")})
        results.append(
            {
                "source": key,
                "label": label,
                "homepage": home,
                "status": h.get("last_status", "error"),
                "detail": h.get("last_detail", ""),
                "items": len(items),
                "latency_ms": latency,
                "sample_titles": [i["title"] for i in items[:3]],
                "websites": [{"name": n, "url": u} for n, u in sites[:8]],
            }
        )
    return results
