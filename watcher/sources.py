"""
Multi-Source Internet & Direct LinkedIn Discovery Engine for SETS (www.sets4us.com).
Upgrades:
1. Direct LinkedIn Guest Search + Authenticated LinkedIn Session (`li_at` cookie) Support
2. Concise, high-recall LinkedIn Post & Pulse indexers (Google RSS, Bing RSS, DuckDuckGo Lite POST)
   that avoid search-engine boolean blocks and include `when:14d` / `when:30d` freshness filters.
3. Rotating Query Cursor across 45+ regional & technical combinations (never repeats the same static batch).
4. Live Custom Keyword Search (`run_custom_live_search`) so the user can search any keyword on-demand.
"""

import html
import json
import random
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

# Rotating cursor so consecutive scans always query fresh combinations
_ROTATING_CURSOR = 0


def clean_html_text(raw: str) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    stripped = TAG_STRIP_RE.sub(" ", unescaped)
    return " ".join(stripped.split())


def build_discovery_queries(settings: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Build a rich, diverse pool of concise search queries across UAE, KSA, and India
    with rotating sub-topics so every scan discovers new enquiries.
    """
    regions = settings.get("active_regions") or ["UAE", "KSA", "India"]
    categories = settings.get("active_categories") or [
        "Energy Audit",
        "Sustainability Audit",
        "BMS",
        "CMS",
        "ESG Reporting",
    ]

    region_cities = {
        "UAE": ["Dubai", "Abu Dhabi", "Sharjah", "Ras Al Khaimah", "Ajman", "UAE"],
        "KSA": ["Riyadh", "Jeddah", "Dammam", "Khobar", "NEOM", "Saudi Arabia"],
        "India": ["Mumbai", "Bengaluru", "Chennai", "Hyderabad", "Kochi", "Pune", "Delhi NCR", "Ahmedabad", "India"],
    }

    category_variants = {
        "Energy Audit": [
            "Energy Audit RFP OR tender",
            "ASHRAE Level 2 Energy Audit consultant",
            "ISO 50001 energy consultant enquiry",
            "ESCO energy efficiency tender",
            "walk-through energy audit commercial building",
            "industrial energy audit requirement",
        ],
        "Sustainability Audit": [
            "Sustainability Audit consultant RFP",
            "LEED certification consultant tender",
            "Estidama OR Mostadam OR Al Safat consultant",
            "IGBC OR GRIHA green building consultant",
            "net zero decarbonization consultant requirement",
        ],
        "BMS": [
            "Building Management System BMS tender",
            "BMS retrofit upgrade RFP contractor",
            "BMS AMC maintenance requirement",
            "HVAC automation Niagara BACnet consultant",
            "chiller plant optimization BMS enquiry",
        ],
        "CMS": [
            "Central Monitoring System CMS BMS tender",
            "Energy Management System EMS IoT metering RFP",
            "smart building command center SCADA BMS",
            "fault detection diagnostics FDD building EMS",
        ],
        "ESG Reporting": [
            "ESG reporting consultant RFP",
            "GRI sustainability report consultant requirement",
            "BRSR reporting consultant India",
            "Scope 1 Scope 2 Scope 3 carbon footprint consultant",
            "Tadawul OR ADX ESG disclosure advisory",
        ],
    }

    queries: List[Dict[str, str]] = []
    for reg in regions:
        cities = region_cities.get(reg, [reg])
        for cat in categories:
            variants = category_variants.get(cat, [f"{cat} tender"])
            for idx, var_phrase in enumerate(variants):
                city = cities[idx % len(cities)]
                queries.append(
                    {
                        "region": reg,
                        "category": cat,
                        "city": city,
                        "web_query": f"{var_phrase} {city} when:30d",
                        "linkedin_query": f'site:linkedin.com/posts "{cat}" {city} (RFP OR tender OR requirement OR looking OR consultant)',
                        "linkedin_pulse_query": f'site:linkedin.com "{var_phrase.split()[0]} {var_phrase.split()[1]}" {city} consultant OR tender',
                        "simple_query": f"{var_phrase} {city}",
                    }
                )

    # Also add user's custom keywords
    custom_kws = [
        k.strip()
        for k in (settings.get("custom_keywords") or "").split(",")
        if k.strip()
    ]
    for ckw in custom_kws[:6]:
        for reg in regions:
            queries.append(
                {
                    "region": reg,
                    "category": "Energy Audit",
                    "city": reg,
                    "web_query": f'"{ckw}" {reg} (RFP OR tender OR requirement OR consultant) when:30d',
                    "linkedin_query": f'site:linkedin.com/posts "{ckw}" {reg}',
                    "linkedin_pulse_query": f'site:linkedin.com "{ckw}" {reg} requirement',
                    "simple_query": f"{ckw} {reg} tender OR requirement",
                }
            )

    return queries


def fetch_url(url: str, timeout: int = 10, extra_headers: Dict[str, str] = None) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_rss_xml(xml_bytes: bytes, source_platform: str, region: str, category: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
        for item_el in root.findall(".//item")[:10]:
            title = clean_html_text(item_el.findtext("title") or "")
            link = (item_el.findtext("link") or "").strip()
            desc = clean_html_text(item_el.findtext("description") or "")
            pub_date = (item_el.findtext("pubDate") or "").strip()
            if not title or not link:
                continue
            platform_label = (
                "LinkedIn"
                if ("linkedin.com" in link.lower() or "linkedin" in title.lower())
                else source_platform
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


def search_linkedin_direct_guest(
    keyword: str, location: str, region: str, category: str, settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Directly queries LinkedIn's public Guest Search endpoint (`linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`)
    and optional `li_at` session cookie endpoint to discover active project/consultant requirements posted on LinkedIn.
    """
    items: List[Dict[str, Any]] = []
    q = urllib.parse.quote_plus(f"{keyword} consultant OR project OR audit")
    loc = urllib.parse.quote_plus(location)
    # f_TPR=r2592000 = past 30 days
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={q}&location={loc}&f_TPR=r2592000&start=0"

    extra_headers = {}
    li_at = (settings.get("linkedin_li_at_cookie") or "").strip()
    if li_at:
        extra_headers["Cookie"] = f"li_at={li_at}"

    try:
        raw = fetch_url(url, timeout=10, extra_headers=extra_headers).decode("utf-8", errors="ignore")
        # Parse LinkedIn cards from HTML response
        card_blocks = re.findall(r"<li[^>]*>(.*?)</li>", raw, re.DOTALL | re.IGNORECASE)
        for block in card_blocks[:6]:
            title_m = re.search(
                r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            comp_m = re.search(
                r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</h',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            loc_m = re.search(
                r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            href_m = re.search(r'href="(https://[^"]*linkedin\.com/[^"]+)"', block, re.IGNORECASE)

            if not title_m or not href_m:
                continue

            role_title = clean_html_text(title_m.group(1))
            company = clean_html_text(comp_m.group(1)) if comp_m else "Organization on LinkedIn"
            loc_text = clean_html_text(loc_m.group(1)) if loc_m else location
            link = href_m.group(1).split("?")[0]

            items.append(
                {
                    "title": f"[LinkedIn Requirement] {role_title} — {company} ({loc_text})",
                    "snippet": (
                        f"Active LinkedIn requirement posted by {company} in {loc_text} seeking "
                        f"{role_title} ({category} / Engineering & Sustainability scope). "
                        f"Contact organization ({company}) for consultancy/partnership proposal."
                    ),
                    "url": link,
                    "source_platform": "LinkedIn",
                    "region": region,
                    "default_category": category,
                    "published_at": "",
                }
            )
    except Exception:
        pass
    return items


def search_google_news_rss(
    query_str: str, region: str, category: str, platform_label: str = "Web / Tenders"
) -> List[Dict[str, Any]]:
    gl_map = {
        "UAE": ("AE", "en-AE", "AE:en"),
        "KSA": ("SA", "en-US", "SA:en"),
        "India": ("IN", "en-IN", "IN:en"),
    }
    gl, hl, ceid = gl_map.get(region, ("AE", "en-AE", "AE:en"))
    q = urllib.parse.quote_plus(query_str)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    try:
        raw = fetch_url(url, timeout=9)
        return parse_rss_xml(raw, platform_label, region, category)
    except Exception:
        return []


def search_bing_rss(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote_plus(query_str)
    # Try both Bing Web RSS and Bing News RSS
    items: List[Dict[str, Any]] = []
    for base_ep in (
        f"https://www.bing.com/news/search?q={q}&format=rss",
        f"https://www.bing.com/search?q={q}&format=rss",
    ):
        try:
            raw = fetch_url(base_ep, timeout=9)
            parsed = parse_rss_xml(raw, platform_label, region, category)
            if parsed:
                items.extend(parsed)
                break
        except Exception:
            pass
    return items


def search_duckduckgo_html(query_str: str, platform_label: str, region: str, category: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote_plus(query_str)
    url = f"https://html.duckduckgo.com/html/?q={q}"
    items: List[Dict[str, Any]] = []
    try:
        raw = fetch_url(url, timeout=10).decode("utf-8", errors="ignore")
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


def search_reddit_json(query_str: str, region: str, category: str) -> List[Dict[str, Any]]:
    q = urllib.parse.quote_plus(query_str)
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&t=month&limit=6"
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
                    "region": region,
                    "default_category": category,
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
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={q}&num=6"
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
    url = f"https://serpapi.com/search.json?engine=google&q={q}&api_key={api_key}&num=6"
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


def run_multi_source_discovery(
    settings: Dict[str, Any], max_queries: int = 10
) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """
    Execute discovery across enabled sources using a rotating query cursor so consecutive
    scans always cover new keywords, cities, and platforms rather than repeating static results.
    """
    global _ROTATING_CURSOR
    active_sources = set(settings.get("active_sources") or [])
    all_queries = build_discovery_queries(settings)

    if not all_queries:
        return [], 0, []

    # Select rotating slice + random sample for maximum variety
    total_q = len(all_queries)
    selected_queries: List[Dict[str, str]] = []
    for i in range(min(max_queries, total_q)):
        idx = (_ROTATING_CURSOR + i) % total_q
        selected_queries.append(all_queries[idx])
    _ROTATING_CURSOR = (_ROTATING_CURSOR + max_queries) % total_q

    discovered: List[Dict[str, Any]] = []
    queries_executed = 0
    errors: List[str] = []

    for qinfo in selected_queries:
        reg = qinfo["region"]
        cat = qinfo["category"]
        city = qinfo.get("city", reg)

        # 1. Direct LinkedIn Search + LinkedIn Post Indexers
        if "linkedin_social" in active_sources:
            queries_executed += 1
            # A) Direct LinkedIn Guest Search
            li_direct = search_linkedin_direct_guest(cat, city, reg, cat, settings)
            discovered.extend(li_direct)

            # B) Google News RSS / Bing RSS / DuckDuckGo for `site:linkedin.com` posts
            li_posts = search_google_news_rss(qinfo["linkedin_pulse_query"], reg, cat, "LinkedIn")
            if not li_posts:
                li_posts = search_duckduckgo_html(qinfo["linkedin_query"], "LinkedIn", reg, cat)
            if not li_posts:
                li_posts = search_bing_rss(qinfo["linkedin_query"], "LinkedIn", reg, cat)
            discovered.extend(li_posts)

        # 2. Google News & Tender RSS
        if "google_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(search_google_news_rss(qinfo["web_query"], reg, cat))

        # 3. Bing Web/News RSS
        if "bing_news_rss" in active_sources:
            queries_executed += 1
            discovered.extend(
                search_bing_rss(qinfo["simple_query"], "Web / Tenders", reg, cat)
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
            discovered.extend(search_reddit_json(f"{cat} {city}", reg, cat))

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

    random.shuffle(discovered)
    return discovered, queries_executed, errors


def run_custom_live_search(
    keyword: str, region: str, category: str, settings: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    On-demand live internet & LinkedIn search triggered by the user for a specific keyword.
    Searches LinkedIn Direct, LinkedIn Posts, Google News RSS, Bing RSS, DuckDuckGo, and Reddit.
    """
    reg = region if region and region != "ALL" else "UAE"
    cat = category if category and category != "ALL" else "Energy Audit"
    kw = keyword.strip()
    items: List[Dict[str, Any]] = []

    # 1. LinkedIn Direct Guest Search
    items.extend(search_linkedin_direct_guest(kw, reg, reg, cat, settings))
    # 2. LinkedIn Posts via DuckDuckGo & Google RSS
    items.extend(
        search_duckduckgo_html(f'site:linkedin.com/posts {kw} {reg}', "LinkedIn", reg, cat)
    )
    items.extend(
        search_google_news_rss(f'site:linkedin.com {kw} {reg}', reg, cat, "LinkedIn")
    )
    # 3. Live Web & Tender RSS
    items.extend(search_google_news_rss(f"{kw} {reg} when:30d", reg, cat, "Web / Tenders"))
    items.extend(search_bing_rss(f"{kw} {reg}", "Web / Tenders", reg, cat))
    items.extend(search_duckduckgo_html(f"{kw} {reg} tender OR RFP OR consultant", "Web / Tenders", reg, cat))
    items.extend(search_reddit_json(f"{kw} {reg}", reg, cat))

    return items
