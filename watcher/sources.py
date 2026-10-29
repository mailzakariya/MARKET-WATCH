"""
Multi-Source Internet & Social Media Discovery Engine for SETS (www.sets4us.com).
Discovers new enquiries, RFPs, tenders, and social posts across LinkedIn, Google News RSS,
Bing Search/News RSS, DuckDuckGo Web Search, Reddit JSON API, Google Custom Search, and SerpAPI.
"""

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

TAG_STRIP_RE = re.compile(r"<[^>]+>")


def clean_html_text(raw: str) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    stripped = TAG_STRIP_RE.sub(" ", unescaped)
    return " ".join(stripped.split())


def build_discovery_queries(settings: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Build targeted search queries combining SETS core services, active regions (UAE, KSA, India),
    and commercial intent signals (RFP, tender, enquiry, looking for, consultant).
    """
    regions = settings.get("active_regions") or ["UAE", "KSA", "India"]
    categories = settings.get("active_categories") or [
        "Energy Audit",
        "Sustainability Audit",
        "BMS",
        "CMS",
        "ESG Reporting",
    ]

    region_terms = {
        "UAE": '("UAE" OR "Dubai" OR "Abu Dhabi")',
        "KSA": '("Saudi Arabia" OR "KSA" OR "Riyadh" OR "Jeddah")',
        "India": '("India" OR "Mumbai" OR "Bengaluru" OR "Delhi")',
    }

    category_terms = {
        "Energy Audit": '("Energy Audit" OR "ASHRAE Audit" OR "ESCO" OR "ISO 50001")',
        "Sustainability Audit": '("Sustainability Audit" OR "LEED consultant" OR "Estidama" OR "Mostadam" OR "Green Building")',
        "BMS": '("Building Management System" OR "BMS tender" OR "BMS retrofit" OR "BMS AMC" OR "HVAC automation")',
        "CMS": '("Central Monitoring System" OR "Energy Management System" OR "IoT energy monitoring" OR "SCADA BMS")',
        "ESG Reporting": '("ESG reporting" OR "ESG consultant" OR "GRI report" OR "BRSR" OR "GHG inventory")',
    }

    intent_clause = '("RFP" OR "RFQ" OR "tender" OR "enquiry" OR "looking for" OR "consultant" OR "vendor")'

    queries: List[Dict[str, str]] = []
    for reg in regions:
        r_clause = region_terms.get(reg, f'"{reg}"')
        for cat in categories:
            c_clause = category_terms.get(cat, f'"{cat}"')
            queries.append(
                {
                    "region": reg,
                    "category": cat,
                    "web_query": f"{c_clause} {r_clause} {intent_clause}",
                    "linkedin_query": f'site:linkedin.com/posts {c_clause} {r_clause} ("looking for" OR "RFP" OR "RFQ" OR "tender" OR "enquiry" OR "consultant")',
                    "simple_query": f"{cat} {reg} tender OR RFP OR consultant",
                }
            )
    return queries


def fetch_url(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_rss_xml(xml_bytes: bytes, source_platform: str, region: str, category: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
        for item_el in root.findall(".//item")[:8]:
            title = clean_html_text(item_el.findtext("title") or "")
            link = (item_el.findtext("link") or "").strip()
            desc = clean_html_text(item_el.findtext("description") or "")
            pub_date = (item_el.findtext("pubDate") or "").strip()
            if not title or not link:
                continue
            platform_label = (
                "LinkedIn" if "linkedin.com" in link.lower() else source_platform
            )
            items.append(
                {
                    "title": title,
                    "snippet": desc or title,
                    "url": link,
                    "source_platform": platform_label,
                    "region": region,
                    "default_category": category,
                    "published_at": pub_date,
                }
            )
    except Exception:
        pass
    return items


def search_google_news_rss(query_info: Dict[str, str]) -> List[Dict[str, Any]]:
    reg = query_info["region"]
    cat = query_info["category"]
    gl_map = {"UAE": ("AE", "en-AE", "AE:en"), "KSA": ("SA", "en-US", "SA:en"), "India": ("IN", "en-IN", "IN:en")}
    gl, hl, ceid = gl_map.get(reg, ("AE", "en-AE", "AE:en"))
    q = urllib.parse.quote_plus(query_info["simple_query"])
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        raw = fetch_url(url, timeout=9)
        return parse_rss_xml(raw, "Web / Tenders", reg, cat)
    except Exception:
        return []


def search_bing_rss(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote_plus(query_str)
    url = f"https://www.bing.com/search?q={q}&format=rss"
    try:
        raw = fetch_url(url, timeout=9)
        return parse_rss_xml(raw, platform_label, region, category)
    except Exception:
        return []


def search_duckduckgo_html(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote_plus(query_str)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=10).decode("utf-8", errors="ignore")
        # Extract result blocks
        link_pattern = re.compile(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        links = link_pattern.findall(raw)
        snippets = snippet_pattern.findall(raw)

        for idx, (href, raw_title) in enumerate(links[:6]):
            actual_url = href
            if "uddg=" in href:
                parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                if "uddg" in parsed_qs:
                    actual_url = parsed_qs["uddg"][0]
            title = clean_html_text(raw_title)
            snippet = clean_html_text(snippets[idx]) if idx < len(snippets) else title
            if not title or not actual_url.startswith("http"):
                continue
            detected_platform = (
                "LinkedIn"
                if "linkedin.com" in actual_url.lower()
                else platform_label
            )
            items.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "url": actual_url,
                    "source_platform": detected_platform,
                    "region": region,
                    "default_category": category,
                    "published_at": "",
                }
            )
    except Exception:
        pass
    return items


def search_reddit_json(query_info: Dict[str, str]) -> List[Dict[str, Any]]:
    reg = query_info["region"]
    cat = query_info["category"]
    q = urllib.parse.quote_plus(f"{cat} {reg}")
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&limit=5"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=9)
        data = json.loads(raw.decode("utf-8", errors="ignore"))
        children = data.get("data", {}).get("children", [])
        for child in children:
            post = child.get("data", {})
            title = clean_html_text(post.get("title") or "")
            selftext = clean_html_text(post.get("selftext") or "")
            permalink = post.get("permalink") or ""
            author = post.get("author") or ""
            subreddit = post.get("subreddit_name_prefixed") or "Reddit"
            if not title or not permalink:
                continue
            full_url = f"https://www.reddit.com{permalink}"
            snippet = f"[{subreddit} | Posted by u/{author}] {selftext or title}"
            items.append(
                {
                    "title": title,
                    "snippet": snippet[:1500],
                    "url": full_url,
                    "source_platform": "Reddit / Social",
                    "region": reg,
                    "default_category": cat,
                    "published_at": "",
                }
            )
    except Exception:
        pass
    return items


def search_google_cse(query_str: str, region: str, category: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    api_key = (settings.get("google_cse_api_key") or "").strip()
    cx = (settings.get("google_cse_cx") or "").strip()
    if not api_key or not cx:
        return []
    q = urllib.parse.quote_plus(query_str)
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={q}&num=5"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=10)
        data = json.loads(raw.decode("utf-8", errors="ignore"))
        for entry in data.get("items", []):
            link = entry.get("link", "")
            items.append(
                {
                    "title": entry.get("title", ""),
                    "snippet": entry.get("snippet", ""),
                    "url": link,
                    "source_platform": "LinkedIn" if "linkedin.com" in link.lower() else "Google Search",
                    "region": region,
                    "default_category": category,
                    "published_at": "",
                }
            )
    except Exception:
        pass
    return items


def search_serpapi(query_str: str, region: str, category: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    api_key = (settings.get("serpapi_key") or "").strip()
    if not api_key:
        return []
    q = urllib.parse.quote_plus(query_str)
    url = f"https://serpapi.com/search.json?engine=google&q={q}&api_key={api_key}&num=5"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=10)
        data = json.loads(raw.decode("utf-8", errors="ignore"))
        for entry in data.get("organic_results", []):
            link = entry.get("link", "")
            items.append(
                {
                    "title": entry.get("title", ""),
                    "snippet": entry.get("snippet", ""),
                    "url": link,
                    "source_platform": "LinkedIn" if "linkedin.com" in link.lower() else "SerpAPI Web",
                    "region": region,
                    "default_category": category,
                    "published_at": "",
                }
            )
    except Exception:
        pass
    return items


def run_multi_source_discovery(settings: Dict[str, Any], max_queries: int = 8) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Execute discovery across enabled sources and return (discovered_items, queries_executed, source_errors).
    """
    active_sources = set(settings.get("active_sources") or [])
    all_queries = build_discovery_queries(settings)
    selected_queries = all_queries[:max_queries]

    discovered: List[Dict[str, Any]] = []
    queries_executed = 0
    errors: List[str] = []

    for qinfo in selected_queries:
        reg = qinfo["region"]
        cat = qinfo["category"]

        # 1. LinkedIn & Social Media Post Discovery
        if "linkedin_social" in active_sources:
            queries_executed += 1
            li_items = search_bing_rss(qinfo["linkedin_query"], "LinkedIn", reg, cat)
            if not li_items:
                li_items = search_duckduckgo_html(qinfo["linkedin_query"], "LinkedIn", reg, cat)
            discovered.extend(li_items)

        # 2. Google News & Tender RSS
        if "google_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(search_google_news_rss(qinfo))

        # 3. Bing Web/News RSS
        if "bing_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(
                search_bing_rss(qinfo["web_query"], "Web / Tenders", reg, cat)
            )

        # 4. DuckDuckGo Web Search
        if "duckduckgo_web" in active_sources:
            queries_executed += 1
            discovered.extend(
                search_duckduckgo_html(qinfo["simple_query"], "Web / Tenders", reg, cat)
            )

        # 5. Reddit Communities
        if "reddit_communities" in active_sources:
            queries_executed += 1
            discovered.extend(search_reddit_json(qinfo))

        # 6. Optional Google CSE / SerpAPI
        if settings.get("google_cse_api_key") and settings.get("google_cse_cx"):
            queries_executed += 1
            discovered.extend(search_google_cse(qinfo["linkedin_query"], reg, cat, settings))
        if settings.get("serpapi_key"):
            queries_executed += 1
            discovered.extend(search_serpapi(qinfo["linkedin_query"], reg, cat, settings))

    # 7. Custom RSS Feeds if provided
    custom_rss = (settings.get("custom_rss_urls") or "").strip()
    if custom_rss:
        for rss_url in [u.strip() for u in custom_rss.splitlines() if u.strip().startswith("http")]:
            try:
                queries_executed += 1
                raw = fetch_url(rss_url, timeout=9)
                discovered.extend(parse_rss_xml(raw, "Custom RSS", "UAE", "Energy Audit"))
            except Exception as exc:
                errors.append(f"Custom RSS ({rss_url}): {exc}")

    return discovered, queries_executed, errors

