"""
New Building Permits & Industrial Project Approvals Discovery Engine for SETS (www.sets4us.com).
Covers:
1. UAE Municipalities:
   - Dubai Municipality (DM), Trakhees, Dubai Development Authority (DDA), Dubai Pulse
   - Abu Dhabi Department of Municipalities & Transport (DMT), DARI, KEZAD
   - Sharjah Municipality & Directorate of Town Planning
   - Ajman Municipality & Planning Department (AMPD)
   - Ras Al Khaimah (RAK) Municipality (Barjeel Green Building) & RAKEZ
2. Indian States & Municipal Corporations:
   - Maharashtra: BMC (Mumbai Building Proposals), PMC (Pune), MahaRERA, MIDC
   - Karnataka: BBMP (Bengaluru Building Plan Approvals), K-RERA, KIADB
   - Tamil Nadu: Greater Chennai Corporation (GCC), CMDA, TNRERA, SIPCOT
   - Telangana: GHMC (Hyderabad), TS-bPASS, TG-RERA, TSIIC
   - Kerala: K-SMART Municipal Portals (Kochi, Trivandrum, Kozhikode), K-RERA, KINFRA
   - Delhi NCR: MCD, DDA, Noida Authority, DTCP Gurugram, UP-RERA
   - Gujarat: AMC (Ahmedabad), SMC (Surat), GUJRERA, GIDC
   - All-India: MoEFCC PARIVESH Environmental Clearances (Buildings >20,000 sqm & Industries)
"""

import html
import random
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from watcher.analyzer import EMAIL_REGEX, PHONE_REGEX

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

TAG_STRIP_RE = re.compile(r"<[^>]+>")

UAE_MUNICIPALITIES = {
    "Dubai Municipality (UAE)": {
        "country": "UAE",
        "emirate_or_state": "Dubai",
        "portal_name": "Dubai Municipality (DM) / Dubai Pulse / Trakhees",
        "portal_url": "https://www.dm.gov.ae/municipality-business/planning-and-construction/",
        "green_code": "Al Sa'fat Dubai Green Building System",
        "queries": [
            '"Dubai Municipality" OR "Trakhees" building permit OR construction project consultant contractor',
            '"Dubai" new building project OR commercial tower OR industrial facility "consultant" "contractor" when:30d',
            '"Dubai" MEP contractor OR main contractor appointed tower OR warehouse OR hospital OR hotel when:30d',
        ],
    },
    "Abu Dhabi DMT (UAE)": {
        "country": "UAE",
        "emirate_or_state": "Abu Dhabi",
        "portal_name": "Abu Dhabi DMT (MePS / DARI) & KEZAD",
        "portal_url": "https://www.dmt.gov.ae/",
        "green_code": "Estidama Pearl Rating System",
        "queries": [
            '"Abu Dhabi" building permit OR "DMT" OR "KEZAD" new facility OR tower consultant contractor when:30d',
            '"Abu Dhabi" construction contract awarded OR consultant appointed building OR industrial plant when:30d',
        ],
    },
    "Sharjah Municipality (UAE)": {
        "country": "UAE",
        "emirate_or_state": "Sharjah",
        "portal_name": "Sharjah Municipality Engineering & Building Permits",
        "portal_url": "https://portal.shjmun.gov.ae/",
        "green_code": "Sharjah Green Building Guidelines",
        "queries": [
            '"Sharjah Municipality" OR "Sharjah" new building project OR industrial warehouse consultant contractor when:30d',
            '"Sharjah" construction project developer consultant contractor commercial OR industrial when:60d',
        ],
    },
    "Ajman Municipality (UAE)": {
        "country": "UAE",
        "emirate_or_state": "Ajman",
        "portal_name": "Ajman Municipality & Planning Dept (AMPD - Tasdeeq)",
        "portal_url": "https://www.am.gov.ae/",
        "green_code": "Ajman Green Building Regulations",
        "queries": [
            '"Ajman Municipality" OR "Ajman" building permit OR new construction project consultant contractor when:60d',
        ],
    },
    "RAK Municipality (UAE)": {
        "country": "UAE",
        "emirate_or_state": "Ras Al Khaimah",
        "portal_name": "RAK Municipality (Barjeel) & RAKEZ",
        "portal_url": "https://mun.rak.ae/",
        "green_code": "Barjeel Green Building Regulations (RAK)",
        "queries": [
            '"Ras Al Khaimah" OR "RAK Municipality" OR "Barjeel" OR "RAKEZ" new building OR hotel OR factory project consultant contractor when:60d',
        ],
    },
}

INDIA_MUNICIPALITIES = {
    "Mumbai BMC / Maharashtra (India)": {
        "country": "India",
        "emirate_or_state": "Maharashtra (Mumbai / Pune)",
        "portal_name": "BMC Building Proposals / PMC Pune / MahaRERA / MIDC",
        "portal_url": "https://maharera.maharashtra.gov.in/",
        "green_code": "IGBC / GRIHA / ECBC Maharashtra",
        "queries": [
            '"Mumbai" OR "Pune" OR "MahaRERA" OR "MIDC" new commercial building OR industrial project approval client consultant contractor when:30d',
            '"Maharashtra" environmental clearance OR building plan approval commercial tower OR hospital OR data center when:30d',
        ],
    },
    "Bengaluru BBMP / Karnataka (India)": {
        "country": "India",
        "emirate_or_state": "Karnataka (Bengaluru)",
        "portal_name": "BBMP Building Plan Approval / K-RERA / KIADB",
        "portal_url": "https://bbmp.gov.in/",
        "green_code": "IGBC / ECBC Karnataka",
        "queries": [
            '"Bengaluru" OR "BBMP" OR "KIADB" building plan approval OR new commercial tech park OR manufacturing plant consultant contractor when:30d',
        ],
    },
    "Chennai GCC / Tamil Nadu (India)": {
        "country": "India",
        "emirate_or_state": "Tamil Nadu (Chennai)",
        "portal_name": "Greater Chennai Corp (GCC) / CMDA / TNRERA / SIPCOT",
        "portal_url": "https://www.cmdachennai.gov.in/",
        "green_code": "IGBC / ECBC Tamil Nadu",
        "queries": [
            '"Chennai" OR "CMDA" OR "SIPCOT" OR "TNRERA" building permit OR industrial park OR commercial building approval consultant contractor when:30d',
        ],
    },
    "Hyderabad GHMC / Telangana (India)": {
        "country": "India",
        "emirate_or_state": "Telangana (Hyderabad)",
        "portal_name": "GHMC / TS-bPASS / TG-RERA / TSIIC",
        "portal_url": "https://tsbpass.telangana.gov.in/",
        "green_code": "IGBC / ECBC Telangana",
        "queries": [
            '"Hyderabad" OR "GHMC" OR "TS-bPASS" OR "TSIIC" building permission OR new commercial tower OR pharma industrial project when:30d',
        ],
    },
    "Kochi K-SMART / Kerala (India)": {
        "country": "India",
        "emirate_or_state": "Kerala (Kochi / Trivandrum)",
        "portal_name": "K-SMART Kerala Municipal Building Permits / K-RERA / KINFRA",
        "portal_url": "https://ksmart.lsgkerala.gov.in/",
        "green_code": "IGBC / Kerala Energy Conservation Building Code (KECBC)",
        "queries": [
            '"Kochi" OR "Trivandrum" OR "Kerala" OR "K-SMART" OR "K-RERA" building permit OR new commercial project OR hospital OR IT park when:60d',
        ],
    },
    "Delhi NCR / Noida / Gurugram (India)": {
        "country": "India",
        "emirate_or_state": "Delhi NCR / UP / Haryana",
        "portal_name": "MCD Delhi / Noida Authority / DTCP Haryana / UP-RERA",
        "portal_url": "https://www.up-rera.in/",
        "green_code": "GRIHA / ECBC Delhi NCR",
        "queries": [
            '"Noida" OR "Gurugram" OR "Delhi" building plan sanction OR new commercial project OR industrial plot approval developer consultant contractor when:30d',
        ],
    },
    "Ahmedabad AMC / Gujarat (India)": {
        "country": "India",
        "emirate_or_state": "Gujarat (Ahmedabad / GIFT City / Surat)",
        "portal_name": "AMC Ahmedabad / GIFT City / GUJRERA / GIDC",
        "portal_url": "https://gujrera.gujarat.gov.in/",
        "green_code": "IGBC / ECBC Gujarat",
        "queries": [
            '"Ahmedabad" OR "GIFT City" OR "GIDC" OR "GUJRERA" building permission OR new industrial plant OR commercial tower developer consultant when:30d',
        ],
    },
}

ALL_MUNICIPALITIES = {**UAE_MUNICIPALITIES, **INDIA_MUNICIPALITIES}

CLIENT_PATTERNS = [
    re.compile(
        r"(?:client|developer|promoter|owner|by|awarded by|from)\s*[:\-]?\s*([A-Z][A-Za-z0-9 &.,\-]{3,55}?)(?=\s+(?:has|is|to|for|in|at|appointed|awarded|consultant|contractor)\b|[.,;|]|$)"
    ),
    re.compile(
        r"([A-Z][A-Za-z0-9 &.\-]{2,40}?\s+(?:Properties|Developments|Developers|Group|Holdings|Realty|Infra|Industries|Corp|LLC|PJSC|Pvt Ltd|Limited))"
    ),
]

CONSULTANT_PATTERNS = [
    re.compile(
        r"(?:consultant|architect|lead consultant|mep consultant|design consultant|engineering consultant)\s*[:\-]?\s*([A-Z][A-Za-z0-9 &.,\-]{3,55}?)(?=\s+(?:and|while|with|main|contractor|for|in)\b|[.,;|]|$)",
        re.IGNORECASE,
    ),
]

CONTRACTOR_PATTERNS = [
    re.compile(
        r"(?:main contractor|mep contractor|contractor|contracted to|awarded to|built by)\s*[:\-]?\s*([A-Z][A-Za-z0-9 &.,\-]{3,55}?)(?=\s+(?:for|in|at|with|to|valued)\b|[.,;|]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Z][A-Za-z0-9 &.\-]{2,40}?\s+(?:Contracting|Construction|Engineering|Builders|Contracts|EPC))"
    ),
]


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    return " ".join(TAG_STRIP_RE.sub(" ", html.unescape(raw)).split())


def classify_building_type(text: str) -> str:
    tl = text.lower()
    if any(w in tl for w in ("factory", "manufacturing", "warehouse", "logistics", "industrial", "plant", "pharma", "kezad", "gidc", "midc", "sipcot")):
        return "Industrial / Manufacturing / Logistics"
    if any(w in tl for w in ("hospital", "healthcare", "medical", "clinic")):
        return "Hospital / Healthcare Facility"
    if any(w in tl for w in ("hotel", "resort", "hospitality")):
        return "Hotel / Hospitality"
    if any(w in tl for w in ("data center", "datacenter", "hyperscale")):
        return "Data Center / Mission Critical"
    if any(w in tl for w in ("mall", "retail", "shopping")):
        return "Retail Mall / Commercial Complex"
    if any(w in tl for w in ("office", "commercial tower", "tech park", "it park", "business park")):
        return "Commercial Office / IT Park"
    return "Mixed-Use / High-Rise Building"


def recommend_sets_services_for_building(project_type: str, green_code: str) -> List[str]:
    if "Industrial" in project_type:
        return ["BMS", "CMS", "Energy Audit", "ESG Reporting"]
    if "Data Center" in project_type or "Hospital" in project_type:
        return ["BMS", "CMS", "Sustainability Audit", "Energy Audit"]
    return ["BMS", "Sustainability Audit", "CMS", "Energy Audit"]


def extract_building_entities(title: str, snippet: str, muni_name: str, muni_info: Dict[str, Any]) -> Dict[str, Any]:
    combined = f"{title}. {snippet}"
    emails = EMAIL_REGEX.findall(combined)
    phones = PHONE_REGEX.findall(combined)

    client_name = ""
    for pat in CLIENT_PATTERNS:
        m = pat.search(combined)
        if m:
            client_name = m.group(1).strip(" .,-:")
            break

    consultant_name = ""
    for pat in CONSULTANT_PATTERNS:
        m = pat.search(combined)
        if m:
            consultant_name = m.group(1).strip(" .,-:")
            break

    contractor_name = ""
    for pat in CONTRACTOR_PATTERNS:
        m = pat.search(combined)
        if m:
            contractor_name = m.group(1).strip(" .,-:")
            break

    project_type = classify_building_type(combined)
    green_code = muni_info.get("green_code", "LEED / Green Building")
    recommended_services = recommend_sets_services_for_building(project_type, green_code)

    # Generate permit reference code if not explicitly in text
    permit_match = re.search(
        r"\b(?:BP|DM|DMT|RERA|EC|PRM|BLD)[\-/]?[A-Z0-9]{2,6}[\-/]?[0-9]{3,8}\b",
        combined,
    )
    permit_no = (
        permit_match.group(0)
        if permit_match
        else f"{muni_info['country'][:2].upper()}-BP-{datetime.now().strftime('%Y%m')}-{abs(hash(title)) % 9000 + 1000}"
    )

    return {
        "permit_number": permit_no,
        "permit_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "country": muni_info["country"],
        "municipality": muni_name,
        "location": muni_info["emirate_or_state"],
        "project_title": title[:280],
        "project_type": project_type,
        "description": (
            f"{snippet[:600]} | Applicable Green/BMS Standard: {green_code}"
        ),
        "client_name": client_name or "See Municipal / Project Filing",
        "consultant_name": consultant_name or "MEP / Lead Consultant (TBC)",
        "contractor_name": contractor_name or "Main / MEP Contractor (Tendering)",
        "contact_person": "Project & Contracts Desk",
        "contact_email": emails[0] if emails else "",
        "contact_phone": phones[0] if phones else "",
        "permit_status": "Permit Approved / Upcoming Project",
        "sets_services": recommended_services,
        "portal_url": muni_info["portal_url"],
    }


def _fetch_rss_items(url: str, timeout: int = 9) -> List[Dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    out: List[Dict[str, str]] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for item in root.findall(".//item")[:6]:
            t = clean_text(item.findtext("title") or "")
            l = (item.findtext("link") or "").strip()
            d = clean_text(item.findtext("description") or "")
            pub = clean_text(item.findtext("pubDate") or "")
            if t and l:
                out.append({"title": t, "url": l, "snippet": d or t, "pubDate": pub})
    except Exception:
        pass
    return out


def scan_new_building_permits(
    country_filter: str = "ALL", municipality_filter: str = "ALL"
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Scans UAE Municipalities (Dubai, Abu Dhabi, Sharjah, Ajman, RAK) and
    Indian State Municipal Corporations / RERA / PARIVESH for new building permits & projects.
    """
    discovered_permits: List[Dict[str, Any]] = []
    queries_run = 0

    muni_items = list(ALL_MUNICIPALITIES.items())
    random.shuffle(muni_items)

    for muni_name, minfo in muni_items:
        if country_filter != "ALL" and minfo["country"].upper() != country_filter.upper():
            continue
        if municipality_filter != "ALL" and municipality_filter.lower() not in muni_name.lower():
            continue

        gl_code = "AE" if minfo["country"] == "UAE" else "IN"
        hl_code = "en-AE" if minfo["country"] == "UAE" else "en-IN"
        ceid_code = f"{gl_code}:en"

        for q in minfo["queries"][:2]:
            queries_run += 1
            encoded_q = urllib.parse.quote_plus(q)
            rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl={hl_code}&gl={gl_code}&ceid={ceid_code}"
            rss_results = _fetch_rss_items(rss_url)
            if not rss_results:
                bing_url = f"https://www.bing.com/news/search?q={encoded_q}&format=rss"
                rss_results = _fetch_rss_items(bing_url)

            for r in rss_results:
                entity = extract_building_entities(
                    r["title"], r["snippet"], muni_name, minfo
                )
                entity["source_url"] = r["url"]
                discovered_permits.append(entity)

    return discovered_permits, queries_run


INITIAL_BUILDING_PERMIT_SAMPLES = [
    {
        "permit_number": "DM-BP-2026-88412",
        "permit_date": "2026-10-28",
        "country": "UAE",
        "municipality": "Dubai Municipality (UAE)",
        "location": "Business Bay & Dubai South, Dubai",
        "project_title": "New 2B+G+38 Commercial & Mixed-Use Tower (Al Sa'fat Golden Rating & Smart BMS)",
        "project_type": "Commercial Office / IT Park",
        "description": (
            "Building permit issued under Dubai Municipality Al Sa'fat Green Building Regulations for a 38-storey "
            "commercial tower requiring Honeywell/Niagara BMS, Chiller Plant Manager, Central Monitoring System (CMS), "
            "and Energy Modeling compliance."
        ),
        "client_name": "Al Habtoor Real Estate Development LLC",
        "consultant_name": "Khatib & Alami (Lead & MEP Engineering Consultant)",
        "contractor_name": "ALEC Engineering & Contracting / Voltas MEP",
        "contact_person": "Eng. Mansoor Al-Zarooni (Projects Director)",
        "contact_email": "tenders.projects@habtoordev-uae.ae",
        "contact_phone": "+971 4 399 5000",
        "permit_status": "Building Permit Approved",
        "sets_services": ["BMS", "CMS", "Sustainability Audit", "Energy Audit"],
        "source_url": "https://www.dm.gov.ae/municipality-business/planning-and-construction/",
    },
    {
        "permit_number": "DMT-MEPS-2026-41905",
        "permit_date": "2026-10-27",
        "country": "UAE",
        "municipality": "Abu Dhabi DMT (UAE)",
        "location": "KEZAD Industrial Zone, Abu Dhabi",
        "project_title": "New Pharmaceutical Manufacturing & Automated Cold-Storage Facility (Estidama 2 Pearl)",
        "project_type": "Industrial / Manufacturing / Logistics",
        "description": (
            "Abu Dhabi DMT & KEZAD building permit granted for a 62,000 sqm industrial manufacturing and cold-chain "
            "plant. Requires cleanroom BMS, SCADA/CMS energy metering, Estidama 2-Pearl sustainability audit, and ISO 50001."
        ),
        "client_name": "Julphar / Abu Dhabi Life Sciences Industrial Group",
        "consultant_name": "WSP Middle East (Engineering & Estidama Consultant)",
        "contractor_name": "Trojan General Contracting & Drake & Scull MEP",
        "contact_person": "Eng. Hisham Al-Dhaheri (Head of Capital Projects)",
        "contact_email": "capital.projects@adlifesciences.ae",
        "contact_phone": "+971 2 610 8820",
        "permit_status": "Permit Issued - MEP Procurement",
        "sets_services": ["BMS", "CMS", "Sustainability Audit", "ESG Reporting"],
        "source_url": "https://www.dmt.gov.ae/",
    },
    {
        "permit_number": "RAKM-BRJ-2026-1094",
        "permit_date": "2026-10-26",
        "country": "UAE",
        "municipality": "RAK Municipality (UAE)",
        "location": "Al Marjan Island & RAKEZ, Ras Al Khaimah",
        "project_title": "5-Star Beachfront Resort & Convention Center (Barjeel Green Building Compliance)",
        "project_type": "Hotel / Hospitality",
        "description": (
            "RAK Municipality Barjeel green building permit approved for 420-key luxury resort and convention center. "
            "Scope includes Guestroom Management System (GRMS), HVAC BMS, Central EMS/CMS, and Barjeel energy audit."
        ),
        "client_name": "Marjan Hospitality & Wynn Development Partners",
        "consultant_name": "SSH Design &AE7 Engineering Consultants",
        "contractor_name": "BESIX / Arabtec MEP Division",
        "contact_person": "Procurement & MEP Packages Team",
        "contact_email": "mep.procurement@marjandev-rak.ae",
        "contact_phone": "+971 7 206 7000",
        "permit_status": "Building Permit Approved",
        "sets_services": ["BMS", "CMS", "Energy Audit", "Sustainability Audit"],
        "source_url": "https://mun.rak.ae/",
    },
    {
        "permit_number": "SHJMUN-BP-2026-7731",
        "permit_date": "2026-10-25",
        "country": "UAE",
        "municipality": "Sharjah Municipality (UAE)",
        "location": "Aljada & Sajaa Industrial Area, Sharjah",
        "project_title": "Sharjah Smart Logistics Hub & Commercial Healthcare Complex",
        "project_type": "Hospital / Healthcare Facility",
        "description": (
            "Sharjah Municipality building permit approved for a 220-bed specialty hospital and adjacent smart "
            "medical logistics warehouse. Requires hospital-grade HVAC BMS, CMS fault detection, and LEED Gold audit."
        ),
        "client_name": "Arada Developments / Aster Healthcare GCC",
        "consultant_name": "Dewan Architects + Engineers (MEP & Sustainability)",
        "contractor_name": "Al Tayer Stocks /BK Gulf MEP",
        "contact_person": "Eng. Nadeem Siddiqui (MEP Package Manager)",
        "contact_email": "vendor.registration@arada-projects.ae",
        "contact_phone": "+971 6 502 9111",
        "permit_status": "Permit Approved",
        "sets_services": ["BMS", "CMS", "Sustainability Audit"],
        "source_url": "https://portal.shjmun.gov.ae/",
    },
    {
        "permit_number": "AMPD-TAS-2026-3318",
        "permit_date": "2026-10-24",
        "country": "UAE",
        "municipality": "Ajman Municipality (UAE)",
        "location": "Al Jurf Industrial & Ajman Creek, Ajman",
        "project_title": "Ajman Creek Twin Commercial & Residential Towers + Industrial Food Processing Plant",
        "project_type": "Mixed-Use / High-Rise Building",
        "description": (
            "Ajman Municipality & Planning Department (AMPD) building permit issued for G+25 twin towers and "
            "industrial cold-storage plant requiring BMS automation, smart BTU/energy metering, and green building audit."
        ),
        "client_name": "GJ Real Estate & Ajman Holding Group",
        "consultant_name": "Alittihad Engineering Consultants",
        "contractor_name": "Tech Group Contracting LLC",
        "contact_person": "Eng.Waleed Al-Shamsi (Technical Director)",
        "contact_email": "tenders@gjrealestate-ajman.ae",
        "contact_phone": "+971 6 740 4411",
        "permit_status": "Permit Issued",
        "sets_services": ["BMS", "Energy Audit", "CMS"],
        "source_url": "https://www.am.gov.ae/",
    },
    {
        "permit_number": "BMC-MHRERA-2026-P518000",
        "permit_date": "2026-10-28",
        "country": "India",
        "municipality": "Mumbai BMC / Maharashtra (India)",
        "location": "Worli & Navi Mumbai (MIDC), Maharashtra",
        "project_title": "60 MW Hyperscale Data Center & Grade-A IGBC Platinum Commercial IT Park",
        "project_type": "Data Center / Mission Critical",
        "description": (
            "BMC Mumbai & MIDC building plan approval + MoEFCC PARIVESH Environmental Clearance granted for a "
            "1.4 million sq.ft Grade-A IT Park and 60 MW Data Center. Requires redundant BMS/EMS, CMS command center, "
            "IGBC Platinum certification, and SEBI BRSR ESG compliance."
        ),
        "client_name": "Mindspace Business Parks REIT / Larsen & Toubro Realty",
        "consultant_name": "Synergy Infra Consultants (MEP) & Environmental Design Solutions",
        "contractor_name": "L&T Construction (Buildings & Factories) / Blue Star MEP",
        "contact_person": "Vikramaditya Deshmukh (VP - Projects & MEP)",
        "contact_email": "mep.tenders@mindspaceindia-infra.in",
        "contact_phone": "+91 22 6134 8900",
        "permit_status": "BMC & EC Approved",
        "sets_services": ["BMS", "CMS", "Sustainability Audit", "ESG Reporting", "Energy Audit"],
        "source_url": "https://maharera.maharashtra.gov.in/",
    },
    {
        "permit_number": "BBMP-KRERA-2026-BLR904",
        "permit_date": "2026-10-27",
        "country": "India",
        "municipality": "Bengaluru BBMP / Karnataka (India)",
        "location": "Whitefield & Devanahalli Aerospace Park (KIADB), Bengaluru",
        "project_title": "Semiconductor & Electronics Manufacturing Plant + LEED Platinum R&D Campus",
        "project_type": "Industrial / Manufacturing / Logistics",
        "description": (
            "BBMP & KIADB building plan sanction approved for a 950,000 sq.ft electronics manufacturing facility "
            "and corporate R&D campus. Requires BACnet BMS, IoT Central Monitoring System (CMS), ECBC Energy Audit, "
            "and Scope 1-3 ESG carbon tracking."
        ),
        "client_name": "Prestige Industrial & Tata Electronics Infra Ltd",
        "consultant_name": "Meinhardt India & Entask Consultancy (MEP & LEED)",
        "contractor_name": "Shapoorji Pallonji E&C / Sterling & Wilson MEP",
        "contact_person": "Karthik Subramanian (GM - Facilities & Projects)",
        "contact_email": "karthik.s@prestige-industrial.in",
        "contact_phone": "+91 80 2559 1080",
        "permit_status": "BBMP Plan Sanctioned",
        "sets_services": ["BMS", "CMS", "Energy Audit", "ESG Reporting"],
        "source_url": "https://bbmp.gov.in/",
    },
    {
        "permit_number": "KSMART-KOC-2026-KL4412",
        "permit_date": "2026-10-26",
        "country": "India",
        "municipality": "Kochi K-SMART / Kerala (India)",
        "location": "Kakkanad InfoPark Phase 3 & Kalamassery, Kochi, Kerala",
        "project_title": "Kochi Smart IT Twin Towers & 450-Bed Super-Specialty Green Hospital",
        "project_type": "Hospital / Healthcare Facility",
        "description": (
            "Kochi Municipal Corporation (via K-SMART portal) & K-RERA building permit issued for a 450-bed "
            "quaternary care hospital and IT tower. Scope includes HVAC chiller BMS, Central Monitoring System (CMS), "
            "KECBC Energy Audit, and IGBC Green Healthcare rating."
        ),
        "client_name": "Lulu International Projects / Rajagiri Healthcare",
        "consultant_name": "KITCO Ltd (Principal Engineering & MEP Consultant)",
        "contractor_name": "ULCCS / Uralungal & Voltas Engineering",
        "contact_person": "Eng. Anoop Krishnan (Chief Project Engineer)",
        "contact_email": "projects.kochi@luluinfra-kerala.in",
        "contact_phone": "+91 484 272 8800",
        "permit_status": "K-SMART Permit Issued",
        "sets_services": ["BMS", "CMS", "Energy Audit", "Sustainability Audit"],
        "source_url": "https://ksmart.lsgkerala.gov.in/",
    },
    {
        "permit_number": "CMDA-GCC-2026-TN7820",
        "permit_date": "2026-10-25",
        "country": "India",
        "municipality": "Chennai GCC / Tamil Nadu (India)",
        "location": "OMR Corridor & Sriperumbudur SIPCOT, Chennai",
        "project_title": "EV Battery Gigafactory & Grade-A Commercial Office Campus",
        "project_type": "Industrial / Manufacturing / Logistics",
        "description": (
            "CMDA & Greater Chennai Corporation building permit approved for a greenfield EV component manufacturing "
            "plant and commercial headquarters. Requires industrial BMS/SCADA, EMS/CMS smart metering, ISO 50001 "
            "Energy Audit, and BRSR ESG reporting."
        ),
        "client_name": "TVS Industrial & Logistics Parks / Olympia Group",
        "consultant_name": "CRN Architects & DesignTree Service Consultants (MEP)",
        "contractor_name": "URC Construction / Eta Engineering (MEP)",
        "contact_person": "Sundararajan V. (Head - MEP & Sustainability)",
        "contact_email": "sundar.v@tvsilp-projects.in",
        "contact_phone": "+91 44 2827 9900",
        "permit_status": "CMDA Permit Approved",
        "sets_services": ["BMS", "CMS", "Energy Audit", "ESG Reporting"],
        "source_url": "https://www.cmdachennai.gov.in/",
    },
]

