"""
Default configuration, service taxonomy, and regional intelligence for
SETS (www.sets4us.com) - Energy Audit, Sustainability, BMS, CMS, and ESG Reporting.
"""

COMPANY_PROFILE = {
    "name": "SETS (Smart Energy & Technical Solutions)",
    "website": "https://www.sets4us.com",
    "description": (
        "Engineering & Sustainability consultancy specializing in Energy Audits, "
        "Sustainability Audits, Building Management Systems (BMS), Central Monitoring "
        "Systems (CMS), and ESG Reporting across UAE, KSA, and India."
    ),
    "services": {
        "Energy Audit": {
            "code": "ENERGY_AUDIT",
            "color": "#10b981",
            "keywords": [
                "energy audit",
                "ASHRAE level 1",
                "ASHRAE level 2",
                "ASHRAE level 3",
                "walk-through energy audit",
                "investment grade audit",
                "industrial energy audit",
                "commercial building energy audit",
                "energy efficiency consultant",
                "retro-commissioning",
                "RCx",
                "ISO 50001 consultant",
                "ESCO tender",
                "energy conservation building code",
                "HVAC energy optimization",
                "thermography audit",
                "power quality audit",
            ],
        },
        "Sustainability Audit": {
            "code": "SUSTAINABILITY",
            "color": "#06b6d4",
            "keywords": [
                "sustainability audit",
                "sustainability consultant",
                "green building certification",
                "LEED consultant",
                "Estidama consultant",
                "Mostadam consultant",
                "Al Sa'fat",
                "IGBC certification",
                "GRIHA rating",
                "net zero roadmap",
                "decarbonization strategy",
                "environmental audit",
                "water audit",
                "waste audit",
            ],
        },
        "BMS": {
            "code": "BMS",
            "color": "#6366f1",
            "keywords": [
                "Building Management System",
                "BMS tender",
                "BMS retrofit",
                "BMS upgrade",
                "BMS AMC",
                "BMS consultant",
                "HVAC automation",
                "smart building controls",
                "BACnet integration",
                "Niagara Tridium",
                "chiller plant manager",
                "building automation system",
                "BAS contractor",
            ],
        },
        "CMS": {
            "code": "CMS",
            "color": "#f59e0b",
            "keywords": [
                "Central Monitoring System",
                "Control and Monitoring System",
                "Energy Management System",
                "EMS implementation",
                "IoT energy monitoring",
                "smart metering system",
                "central command center",
                "fault detection and diagnostics",
                "FDD building",
                "SCADA BMS integration",
                "facility monitoring system",
            ],
        },
        "ESG Reporting": {
            "code": "ESG",
            "color": "#ec4899",
            "keywords": [
                "ESG reporting",
                "ESG consultant",
                "ESG advisory",
                "sustainability report GRI",
                "BRSR reporting",
                "Scope 1 Scope 2 Scope 3",
                "GHG inventory",
                "carbon footprint calculation",
                "carbon accounting",
                "ESG disclosure",
                "TCFD report",
                "CSRD readiness",
            ],
        },
    },
    "regions": {
        "UAE": {
            "name": "United Arab Emirates",
            "locations": [
                "UAE", "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah",
                "Fujairah", "DEWA", "ADDC", "Etihad ESCO", "ADNOC", "Emaar", "Aldar"
            ],
            "phone_prefixes": ["+971", "00971", "050", "052", "054", "055", "056", "058"],
        },
        "KSA": {
            "name": "Saudi Arabia (KSA)",
            "locations": [
                "Saudi Arabia", "KSA", "Riyadh", "Jeddah", "Dammam", "Khobar",
                "NEOM", "Red Sea", "Qiddiya", "Aramco", "SABIC", "Tarshid", "Etimad"
            ],
            "phone_prefixes": ["+966", "00966", "050", "053", "054", "055", "056", "059"],
        },
        "India": {
            "name": "India",
            "locations": [
                "India", "Mumbai", "Delhi", "NCR", "Bengaluru", "Bangalore",
                "Chennai", "Hyderabad", "Pune", "Ahmedabad", "Kolkata", "Kochi", "Kerala", "BEE", "SEBI BRSR"
            ],
            "phone_prefixes": ["+91", "0091"],
        },
    },
    "intent_signals": [
        "looking for",
        "requirement",
        "enquiry",
        "inquiry",
        "RFP",
        "RFQ",
        "EOI",
        "tender",
        "bid",
        "quotation",
        "proposal",
        "vendor registration",
        "consultant needed",
        "seeking",
        "recommend a",
        "hiring consultant",
        "partner required",
        "scope of work",
        "expression of interest",
    ],
}

DEFAULT_SETTINGS = {
    # PostgreSQL Database Configuration (Supports Free Cloud Postgres: Neon.tech, Supabase, Aiven, or Local Postgres)
    "db_engine": "postgresql",  # postgresql (with auto local fallback if server unreachable)
    "postgres_url": "postgresql://postgres:postgres@localhost:5432/sets_watcher",
    "postgres_host": "localhost",
    "postgres_port": 5432,
    "postgres_db": "sets_watcher",
    "postgres_user": "postgres",
    "postgres_password": "",
    "postgres_sslmode": "prefer",

    # Watcher schedule & anti-duplication settings
    "watcher_enabled": True,
    "scan_interval_minutes": 30,
    "min_relevance_score": 55,
    "auto_notify_min_score": 65,
    "dedup_similarity_threshold": 0.62,  # Blocks similar/reposted enquiries (0.50 to 0.90)
    "active_regions": ["UAE", "KSA", "India"],
    "active_categories": [
        "Energy Audit",
        "Sustainability Audit",
        "BMS",
        "CMS",
        "ESG Reporting",
    ],
    "active_sources": [
        "linkedin_social",
        "google_news_rss",
        "bing_news_rss",
        "duckduckgo_web",
        "reddit_communities",
    ],
    "custom_keywords": "ASHRAE audit, BMS AMC, ESG consultant, LEED, Estidama, Mostadam, BRSR",
    "custom_rss_urls": "",

    # AI Configuration (Google Gemini)
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",

    # Optional Paid/Custom Search APIs & Direct LinkedIn Cookie
    "linkedin_li_at_cookie": "",
    "google_cse_api_key": "",
    "google_cse_cx": "",
    "serpapi_key": "",

    # Email Notification Settings
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_use_tls": True,
    "smtp_username": "",
    "smtp_password": "",
    "email_from": "",
    "email_to": "",

    # WhatsApp Notification Settings (Pre-configured with Open-Source Free Bridge & +918138858961)
    "whatsapp_enabled": True,
    "whatsapp_provider": "opensource_bridge",  # opensource_bridge | waha | callmebot | meta_cloud | twilio | webhook
    "whatsapp_recipient_phone": "+918138858961",
    # Open-Source WhatsApp Bridge (Baileys / whatsapp-web.js / WAHA)
    "opensource_bridge_url": "http://127.0.0.1:3001/send",
    "waha_api_url": "http://127.0.0.1:3000/api/sendText",
    "waha_session": "default",
    "waha_api_key": "",
    # CallMeBot / Webhook
    "callmebot_api_key": "",
    "whatsapp_webhook_url": "",
    # Meta WhatsApp Cloud API
    "meta_phone_number_id": "",
    "meta_access_token": "",
    # Twilio WhatsApp API
    "twilio_account_sid": "",
    "twilio_auth_token": "",
    "twilio_from_number": "whatsapp:+14155238886",
}

DEFAULT_TEAM_CONTACTS = [
    {
        "name": "Primary WhatsApp Admin (India)",
        "role": "SETS Lead Coordinator",
        "phone": "+918138858961",
        "email": "",
        "region_filter": "ALL",
        "notify_whatsapp": True,
        "notify_email": False,
        "active": True,
    }
]
