"""
PostgreSQL Database Engine (with automatic local fallback) for SETS AI Lead Watcher.
Provides:
1. Free PostgreSQL support (Neon.tech, Supabase, Aiven, Local PostgreSQL via psycopg2/psycopg/pg8000)
2. Multi-Layer Semantic Anti-Duplication Engine (blocks identical and similar reposted enquiries)
3. Historical Database Search across all past enquiries
4. Team Contacts CRUD (Add, Edit, Delete WhatsApp numbers & Email addresses, pre-configured with +918138858961)
"""

import difflib
import hashlib
import json
import os
import re
import sqlite3
import threading
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from watcher.config import DEFAULT_SETTINGS, DEFAULT_TEAM_CONTACTS

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LOCAL_CFG_PATH = os.path.join(DB_DIR, "postgres_config.json")
FALLBACK_DB_PATH = os.path.join(DB_DIR, "sets_watcher_pgcache.db")

_db_lock = threading.Lock()

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "are", "our", "your",
    "looking", "seeking", "need", "required", "requirement", "enquiry", "inquiry",
    "please", "contact", "send", "share", "post", "posted", "activity", "linkedin",
    "http", "https", "www", "com", "org", "net", "in", "ae", "sa", "on", "at", "to", "of",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_pg_bootstrap_config() -> Dict[str, Any]:
    os.makedirs(DB_DIR, exist_ok=True)
    cfg = {
        "postgres_url": os.environ.get("DATABASE_URL") or DEFAULT_SETTINGS["postgres_url"],
        "postgres_host": os.environ.get("PGHOST") or DEFAULT_SETTINGS["postgres_host"],
        "postgres_port": int(os.environ.get("PGPORT") or DEFAULT_SETTINGS["postgres_port"]),
        "postgres_db": os.environ.get("PGDATABASE") or DEFAULT_SETTINGS["postgres_db"],
        "postgres_user": os.environ.get("PGUSER") or DEFAULT_SETTINGS["postgres_user"],
        "postgres_password": os.environ.get("PGPASSWORD") or DEFAULT_SETTINGS["postgres_password"],
        "postgres_sslmode": os.environ.get("PGSSLMODE") or DEFAULT_SETTINGS["postgres_sslmode"],
    }
    if os.path.isfile(LOCAL_CFG_PATH):
        try:
            with open(LOCAL_CFG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update({k: v for k, v in saved.items() if v is not None})
        except Exception:
            pass
    return cfg


def save_pg_bootstrap_config(cfg: Dict[str, Any]) -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    keys = [
        "postgres_url",
        "postgres_host",
        "postgres_port",
        "postgres_db",
        "postgres_user",
        "postgres_password",
        "postgres_sslmode",
    ]
    current = load_pg_bootstrap_config()
    for k in keys:
        if k in cfg:
            current[k] = cfg[k]
    with open(LOCAL_CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)


def _try_connect_postgres(cfg: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Any], str, str]:
    """
    Attempt to connect to PostgreSQL using psycopg2, psycopg (v3), or pg8000.
    Returns (connection, driver_name, status_message).
    """
    c = cfg or load_pg_bootstrap_config()
    pg_url = (c.get("postgres_url") or "").strip()

    # Parse URL if provided
    host = c.get("postgres_host") or "localhost"
    port = int(c.get("postgres_port") or 5432)
    dbname = c.get("postgres_db") or "sets_watcher"
    user = c.get("postgres_user") or "postgres"
    password = c.get("postgres_password") or ""
    sslmode = c.get("postgres_sslmode") or "prefer"

    if pg_url.startswith("postgres://") or pg_url.startswith("postgresql://"):
        parsed = urllib.parse.urlparse(pg_url)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = int(parsed.port)
        if parsed.path and parsed.path.lstrip("/"):
            dbname = parsed.path.lstrip("/")
        if parsed.username:
            user = urllib.parse.unquote(parsed.username)
        if parsed.password:
            password = urllib.parse.unquote(parsed.password)
        qs = urllib.parse.parse_qs(parsed.query)
        if "sslmode" in qs:
            sslmode = qs["sslmode"][0]

    # 1. Try psycopg2
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            sslmode=sslmode,
            connect_timeout=4,
        )
        return conn, "psycopg2", f"Connected to PostgreSQL ({user}@{host}:{port}/{dbname})"
    except ImportError:
        pass
    except Exception as exc:
        return None, "psycopg2", f"PostgreSQL connection error ({host}:{port}/{dbname}): {exc}"

    # 2. Try psycopg (v3)
    try:
        import psycopg

        conn = psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=4,
        )
        return conn, "psycopg3", f"Connected to PostgreSQL ({user}@{host}:{port}/{dbname})"
    except ImportError:
        pass
    except Exception as exc:
        return None, "psycopg3", f"PostgreSQL connection error ({host}:{port}/{dbname}): {exc}"

    # 3. Try pg8000 (Pure Python PostgreSQL driver)
    try:
        import pg8000.dbapi

        ssl_context = True if sslmode in ("require", "verify-full") else None
        conn = pg8000.dbapi.connect(
            host=host,
            port=port,
            database=dbname,
            user=user,
            password=password,
            timeout=4,
            ssl_context=ssl_context,
        )
        return conn, "pg8000", f"Connected to PostgreSQL ({user}@{host}:{port}/{dbname})"
    except ImportError:
        return (
            None,
            "none",
            "PostgreSQL Python driver (psycopg2-binary / pg8000) not installed or server offline; using local SQL cache.",
        )
    except Exception as exc:
        return None, "pg8000", f"PostgreSQL connection error ({host}:{port}/{dbname}): {exc}"


class UnifiedDBSession:
    """
    Provides a unified SQL interface over PostgreSQL (primary) and SQLite-compatible PostgreSQL cache
    so all queries work seamlessly whether connected to Neon/Supabase/Local PostgreSQL or offline.
    """

    def __init__(self) -> None:
        self.pg_conn, self.driver, self.status_msg = _try_connect_postgres()
        self.is_postgres = self.pg_conn is not None
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        if not self.is_postgres:
            os.makedirs(DB_DIR, exist_ok=True)
            self.sqlite_conn = sqlite3.connect(
                FALLBACK_DB_PATH, timeout=20.0, check_same_thread=False
            )
            self.sqlite_conn.row_factory = sqlite3.Row

    def execute_fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        if self.is_postgres:
            pg_sql = sql.replace("?", "%s")
            cur = self.pg_conn.cursor()
            cur.execute(pg_sql, params)
            if cur.description is None:
                return []
            cols = [col[0] for col in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        else:
            cur = self.sqlite_conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def execute_fetchone(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        rows = self.execute_fetchall(sql, params)
        return rows[0] if rows else None

    def execute_write(
        self, sql: str, params: Tuple[Any, ...] = (), return_id: bool = False
    ) -> Tuple[int, Optional[int]]:
        if self.is_postgres:
            pg_sql = sql.replace("?", "%s")
            if return_id and "RETURNING id" not in pg_sql.upper():
                pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            cur = self.pg_conn.cursor()
            cur.execute(pg_sql, params)
            rowcount = cur.rowcount
            new_id = None
            if return_id:
                fetched = cur.fetchone()
                if fetched:
                    new_id = fetched[0]
            self.pg_conn.commit()
            return rowcount, new_id
        else:
            cur = self.sqlite_conn.cursor()
            cur.execute(sql, params)
            self.sqlite_conn.commit()
            return cur.rowcount, cur.lastrowid if return_id else None

    def close(self) -> None:
        try:
            if self.pg_conn:
                self.pg_conn.close()
            if self.sqlite_conn:
                self.sqlite_conn.close()
        except Exception:
            pass


def get_db_status() -> Dict[str, Any]:
    cfg = load_pg_bootstrap_config()
    conn, driver, msg = _try_connect_postgres(cfg)
    connected = conn is not None
    if conn:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "engine": "PostgreSQL (Active)" if connected else "PostgreSQL (Local Cache Active - Ready for PG Server)",
        "is_postgres_live": connected,
        "driver": driver,
        "message": msg,
        "postgres_url": cfg.get("postgres_url", ""),
        "postgres_host": cfg.get("postgres_host", "localhost"),
        "postgres_port": cfg.get("postgres_port", 5432),
        "postgres_db": cfg.get("postgres_db", "sets_watcher"),
        "postgres_user": cfg.get("postgres_user", "postgres"),
    }


def test_postgres_connection(custom_cfg: Dict[str, Any]) -> Dict[str, Any]:
    conn, driver, msg = _try_connect_postgres(custom_cfg)
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute("SELECT version()")
            ver = cur.fetchone()[0]
            conn.close()
            save_pg_bootstrap_config(custom_cfg)
            init_db()
            return {
                "ok": True,
                "driver": driver,
                "message": f"Connected to PostgreSQL! Server: {ver[:65]}",
            }
        except Exception as exc:
            return {"ok": False, "driver": driver, "message": f"Query failed: {exc}"}
    return {"ok": False, "driver": driver, "message": msg}


# ============================================================================
# ANTI-DUPLICATION & SEMANTIC SIMILARITY ENGINE
# ============================================================================

def normalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = u.split("?")[0].split("#")[0].rstrip("/")
    return u


def normalize_text_tokens(text: str) -> List[str]:
    if not text:
        return []
    words = re.findall(r"[a-z0-9]{3,}", text.lower())
    return [w for w in words if w not in STOPWORDS]


def compute_fingerprint(url: str, title: str) -> str:
    norm_u = normalize_url(url)
    tokens = sorted(set(normalize_text_tokens(title)))
    norm_t = " ".join(tokens) if tokens else (title or "").strip().lower()
    raw = f"{norm_u}||{norm_t}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compute_title_signature(title: str) -> str:
    tokens = sorted(set(normalize_text_tokens(title)))
    return " ".join(tokens[:16])


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """
    Hybrid similarity score (0.0 to 1.0) combining:
    1. Token Jaccard overlap (order-independent keyword matching)
    2. SequenceMatcher character ratio (catches minor rewording/truncation)
    """
    tokens_a = set(normalize_text_tokens(text_a))
    tokens_b = set(normalize_text_tokens(text_b))
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    jaccard = intersection / union if union else 0.0

    # Containment score (if one title is a subset of a longer title)
    min_len = min(len(tokens_a), len(tokens_b))
    containment = intersection / min_len if min_len >= 4 else jaccard

    seq_ratio = difflib.SequenceMatcher(
        None, " ".join(sorted(tokens_a)), " ".join(sorted(tokens_b))
    ).ratio()

    return max(jaccard, (jaccard * 0.5 + seq_ratio * 0.5), containment * 0.85)


def check_duplicate_or_similar_lead(
    candidate: Dict[str, Any], similarity_threshold: float = 0.62
) -> Tuple[bool, Optional[Dict[str, Any]], float, str]:
    """
    Checks the database for any existing enquiry that is identical or semantically similar.
    Returns (is_duplicate, matched_lead_dict, similarity_score, reason).
    """
    cand_url = normalize_url(candidate.get("url", ""))
    cand_title = (candidate.get("title") or "").strip()
    cand_snippet = (candidate.get("snippet") or "").strip()
    cand_fp = compute_fingerprint(candidate.get("url", ""), cand_title)
    cand_email = (candidate.get("poc_email") or "").strip().lower()
    cand_phone = re.sub(r"[^0-9]", "", candidate.get("poc_phone") or "")
    cand_cat = candidate.get("category") or ""

    with _db_lock:
        session = UnifiedDBSession()
        try:
            # 1. Fast exact fingerprint check
            exact = session.execute_fetchone(
                "SELECT id, title, url, discovered_at FROM leads WHERE fingerprint = ?",
                (cand_fp,),
            )
            if exact:
                return True, exact, 1.0, f"Exact match with Lead #{exact['id']}"

            # 2. Check recent 500 enquiries for URL, POC, or semantic title/content similarity
            existing_rows = session.execute_fetchall(
                """
                SELECT id, title, snippet, url, category, region, poc_email, poc_phone, discovered_at
                FROM leads
                ORDER BY id DESC
                LIMIT 500
                """
            )

            for row in existing_rows:
                # Canonical URL check (ignore manual-lead synthetic URLs)
                row_url = normalize_url(row.get("url", ""))
                if (
                    cand_url
                    and row_url
                    and "sets4us.com/manual-lead" not in cand_url
                    and cand_url == row_url
                ):
                    return True, row, 1.0, f"Identical Source URL as Lead #{row['id']}"

                # Title similarity check
                title_sim = compute_text_similarity(cand_title, row.get("title", ""))
                if title_sim >= similarity_threshold:
                    return (
                        True,
                        row,
                        round(title_sim, 2),
                        f"Similar Title ({int(title_sim * 100)}% match) to Lead #{row['id']}: '{row.get('title', '')[:60]}'",
                    )

                # Combined Title + Snippet similarity check
                cand_full = f"{cand_title} {cand_snippet[:400]}"
                row_full = f"{row.get('title', '')} {(row.get('snippet') or '')[:400]}"
                full_sim = compute_text_similarity(cand_full, row_full)
                if full_sim >= (similarity_threshold + 0.05):
                    return (
                        True,
                        row,
                        round(full_sim, 2),
                        f"Similar Enquiry Content ({int(full_sim * 100)}% match) to Lead #{row['id']}",
                    )

                # Same POC Email/Phone + Same Service Category + Moderate overlap
                row_email = (row.get("poc_email") or "").strip().lower()
                row_phone = re.sub(r"[^0-9]", "", row.get("poc_phone") or "")
                same_poc = (cand_email and cand_email == row_email) or (
                    len(cand_phone) >= 8 and cand_phone == row_phone
                )
                if same_poc and cand_cat == row.get("category") and max(title_sim, full_sim) >= 0.42:
                    return (
                        True,
                        row,
                        round(max(title_sim, full_sim), 2),
                        f"Duplicate enquiry from same Point of Contact ({cand_email or cand_phone}) in Lead #{row['id']}",
                    )

            return False, None, 0.0, ""
        finally:
            session.close()


# ============================================================================
# DATABASE INITIALIZATION & SCHEMA (POSTGRESQL + LOCAL CACHE)
# ============================================================================

def init_db() -> None:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            id_col = (
                "SERIAL PRIMARY KEY"
                if session.is_postgres
                else "INTEGER PRIMARY KEY AUTOINCREMENT"
            )
            insert_ignore = (
                "ON CONFLICT (key) DO NOTHING"
                if session.is_postgres
                else "OR IGNORE"
            )

            session.execute_write(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            session.execute_write(
                f"""
                CREATE TABLE IF NOT EXISTS leads (
                    id {id_col},
                    fingerprint TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    category TEXT NOT NULL,
                    matched_services TEXT NOT NULL,
                    region TEXT NOT NULL,
                    relevance_score INTEGER NOT NULL,
                    urgency TEXT NOT NULL,
                    is_genuine_enquiry INTEGER NOT NULL DEFAULT 1,
                    ai_summary TEXT NOT NULL,
                    poc_name TEXT DEFAULT '',
                    poc_role TEXT DEFAULT '',
                    poc_company TEXT DEFAULT '',
                    poc_email TEXT DEFAULT '',
                    poc_phone TEXT DEFAULT '',
                    poc_linkedin TEXT DEFAULT '',
                    poc_location TEXT DEFAULT '',
                    suggested_pitch TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'New',
                    notified_email INTEGER NOT NULL DEFAULT 0,
                    notified_whatsapp INTEGER NOT NULL DEFAULT 0,
                    analyzed_by TEXT NOT NULL DEFAULT 'hybrid',
                    published_at TEXT DEFAULT '',
                    discovered_at TEXT NOT NULL
                )
                """
            )
            session.execute_write(
                f"""
                CREATE TABLE IF NOT EXISTS team_contacts (
                    id {id_col},
                    name TEXT NOT NULL,
                    role TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    region_filter TEXT DEFAULT 'ALL',
                    notify_whatsapp INTEGER NOT NULL DEFAULT 1,
                    notify_email INTEGER NOT NULL DEFAULT 1,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            session.execute_write(
                f"""
                CREATE TABLE IF NOT EXISTS scan_logs (
                    id {id_col},
                    trigger_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    queries_run INTEGER DEFAULT 0,
                    raw_items_found INTEGER DEFAULT 0,
                    duplicates_skipped INTEGER DEFAULT 0,
                    new_leads_saved INTEGER DEFAULT 0,
                    notifications_sent INTEGER DEFAULT 0,
                    details TEXT DEFAULT ''
                )
                """
            )
            session.execute_write(
                f"""
                CREATE TABLE IF NOT EXISTS notification_logs (
                    id {id_col},
                    lead_id INTEGER,
                    channel TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message_preview TEXT NOT NULL,
                    error_detail TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )

            # Ensure default settings exist
            now = utc_now_iso()
            existing_keys = {
                r["key"] for r in session.execute_fetchall("SELECT key FROM settings")
            }
            for k, v in DEFAULT_SETTINGS.items():
                if k not in existing_keys:
                    session.execute_write(
                        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                        (k, json.dumps(v), now),
                    )

            # Ensure default team contact (+918138858961) exists if team_contacts is empty
            cnt_row = session.execute_fetchone("SELECT COUNT(*) as cnt FROM team_contacts")
            if not cnt_row or int(cnt_row["cnt"]) == 0:
                for tc in DEFAULT_TEAM_CONTACTS:
                    session.execute_write(
                        """
                        INSERT INTO team_contacts (
                            name, role, phone, email, region_filter,
                            notify_whatsapp, notify_email, active, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tc["name"],
                            tc["role"],
                            tc["phone"],
                            tc["email"],
                            tc["region_filter"],
                            1 if tc["notify_whatsapp"] else 0,
                            1 if tc["notify_email"] else 0,
                            1 if tc["active"] else 0,
                            now,
                        ),
                    )
        finally:
            session.close()

    seed_initial_leads_if_empty()


# ============================================================================
# TEAM CONTACTS CRUD (NUMBERS & EMAILS CONFIGURATION)
# ============================================================================

def list_team_contacts(active_only: bool = False) -> List[Dict[str, Any]]:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            sql = "SELECT * FROM team_contacts"
            if active_only:
                sql += " WHERE active = 1"
            sql += " ORDER BY id ASC"
            rows = session.execute_fetchall(sql)
            for r in rows:
                r["notify_whatsapp"] = bool(r.get("notify_whatsapp"))
                r["notify_email"] = bool(r.get("notify_email"))
                r["active"] = bool(r.get("active"))
            return rows
        finally:
            session.close()


def add_team_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now_iso()
    name = (contact.get("name") or "Team Member").strip()
    role = (contact.get("role") or "").strip()
    phone = (contact.get("phone") or "").strip()
    email = (contact.get("email") or "").strip()
    region_filter = (contact.get("region_filter") or "ALL").strip()
    notify_wa = 1 if contact.get("notify_whatsapp", True) else 0
    notify_em = 1 if contact.get("notify_email", True) else 0
    active = 1 if contact.get("active", True) else 0

    with _db_lock:
        session = UnifiedDBSession()
        try:
            _, new_id = session.execute_write(
                """
                INSERT INTO team_contacts (
                    name, role, phone, email, region_filter,
                    notify_whatsapp, notify_email, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, role, phone, email, region_filter, notify_wa, notify_em, active, now),
                return_id=True,
            )
            return {"ok": True, "id": new_id}
        finally:
            session.close()


def update_team_contact(contact_id: int, contact: Dict[str, Any]) -> bool:
    name = (contact.get("name") or "Team Member").strip()
    role = (contact.get("role") or "").strip()
    phone = (contact.get("phone") or "").strip()
    email = (contact.get("email") or "").strip()
    region_filter = (contact.get("region_filter") or "ALL").strip()
    notify_wa = 1 if contact.get("notify_whatsapp", True) else 0
    notify_em = 1 if contact.get("notify_email", True) else 0
    active = 1 if contact.get("active", True) else 0

    with _db_lock:
        session = UnifiedDBSession()
        try:
            rowcount, _ = session.execute_write(
                """
                UPDATE team_contacts
                SET name = ?, role = ?, phone = ?, email = ?, region_filter = ?,
                    notify_whatsapp = ?, notify_email = ?, active = ?
                WHERE id = ?
                """,
                (
                    name,
                    role,
                    phone,
                    email,
                    region_filter,
                    notify_wa,
                    notify_em,
                    active,
                    int(contact_id),
                ),
            )
            return rowcount > 0
        finally:
            session.close()


def delete_team_contact(contact_id: int) -> bool:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            rowcount, _ = session.execute_write(
                "DELETE FROM team_contacts WHERE id = ?", (int(contact_id),)
            )
            return rowcount > 0
        finally:
            session.close()


# ============================================================================
# SETTINGS & LEADS OPERATIONS
# ============================================================================

def get_settings() -> Dict[str, Any]:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            rows = session.execute_fetchall("SELECT key, value FROM settings")
            result = dict(DEFAULT_SETTINGS)
            for row in rows:
                try:
                    result[row["key"]] = json.loads(row["value"])
                except Exception:
                    result[row["key"]] = row["value"]
            return result
        finally:
            session.close()


def update_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    now = utc_now_iso()
    # Save PostgreSQL connection parameters if updated
    if any(k.startswith("postgres_") for k in updates):
        save_pg_bootstrap_config(updates)

    with _db_lock:
        session = UnifiedDBSession()
        try:
            for k, v in updates.items():
                if k in DEFAULT_SETTINGS:
                    existing = session.execute_fetchone(
                        "SELECT key FROM settings WHERE key = ?", (k,)
                    )
                    if existing:
                        session.execute_write(
                            "UPDATE settings SET value = ?, updated_at = ? WHERE key = ?",
                            (json.dumps(v), now, k),
                        )
                    else:
                        session.execute_write(
                            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                            (k, json.dumps(v), now),
                        )
        finally:
            session.close()
    return get_settings()


def insert_lead(
    lead: Dict[str, Any], check_duplicates: bool = True, similarity_threshold: float = 0.62
) -> Tuple[Optional[int], Optional[str]]:
    """
    Checks for duplicate or similar leads in the database first, then inserts if unique.
    Returns (new_lead_id_or_None, duplicate_reason_or_None).
    """
    if check_duplicates:
        is_dup, matched, score, reason = check_duplicate_or_similar_lead(
            lead, similarity_threshold=similarity_threshold
        )
        if is_dup:
            return None, reason

    fp = compute_fingerprint(lead.get("url", ""), lead.get("title", ""))
    now = utc_now_iso()
    matched_services = lead.get("matched_services", [lead.get("category", "Energy Audit")])
    matched_services_str = (
        json.dumps(matched_services)
        if isinstance(matched_services, list)
        else str(matched_services)
    )

    with _db_lock:
        session = UnifiedDBSession()
        try:
            existing = session.execute_fetchone(
                "SELECT id FROM leads WHERE fingerprint = ?", (fp,)
            )
            if existing:
                return None, f"Exact fingerprint match with Lead #{existing['id']}"

            _, new_id = session.execute_write(
                """
                INSERT INTO leads (
                    fingerprint, title, snippet, url, source_platform,
                    category, matched_services, region, relevance_score, urgency,
                    is_genuine_enquiry, ai_summary,
                    poc_name, poc_role, poc_company, poc_email, poc_phone,
                    poc_linkedin, poc_location, suggested_pitch,
                    status, notified_email, notified_whatsapp,
                    analyzed_by, published_at, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fp,
                    lead.get("title", "Untitled Enquiry")[:300],
                    lead.get("snippet", "")[:2500],
                    lead.get("url", ""),
                    lead.get("source_platform", "Web"),
                    lead.get("category", "Energy Audit"),
                    matched_services_str,
                    lead.get("region", "UAE"),
                    int(lead.get("relevance_score", 60)),
                    lead.get("urgency", "Medium"),
                    1 if lead.get("is_genuine_enquiry", True) else 0,
                    lead.get("ai_summary", ""),
                    lead.get("poc_name", ""),
                    lead.get("poc_role", ""),
                    lead.get("poc_company", ""),
                    lead.get("poc_email", ""),
                    lead.get("poc_phone", ""),
                    lead.get("poc_linkedin", ""),
                    lead.get("poc_location", ""),
                    lead.get("suggested_pitch", ""),
                    lead.get("status", "New"),
                    int(lead.get("notified_email", 0)),
                    int(lead.get("notified_whatsapp", 0)),
                    lead.get("analyzed_by", "hybrid"),
                    lead.get("published_at", now),
                    lead.get("discovered_at", now),
                ),
                return_id=True,
            )
            return new_id, None
        finally:
            session.close()


def mark_lead_notified(lead_id: int, channel: str) -> None:
    col = "notified_email" if channel == "email" else "notified_whatsapp"
    with _db_lock:
        session = UnifiedDBSession()
        try:
            session.execute_write(
                f"UPDATE leads SET {col} = 1 WHERE id = ?", (int(lead_id),)
            )
        finally:
            session.close()


def update_lead_status(lead_id: int, status: str) -> bool:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            rc, _ = session.execute_write(
                "UPDATE leads SET status = ? WHERE id = ?", (status, int(lead_id))
            )
            return rc > 0
        finally:
            session.close()


def delete_lead(lead_id: int) -> bool:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            rc, _ = session.execute_write(
                "DELETE FROM leads WHERE id = ?", (int(lead_id),)
            )
            return rc > 0
        finally:
            session.close()


def list_leads(
    category: str = "",
    region: str = "",
    platform: str = "",
    status: str = "",
    min_score: int = 0,
    search_query: str = "",
    date_from: str = "",
    date_to: str = "",
    has_poc: str = "",
    limit: int = 250,
) -> List[Dict[str, Any]]:
    clauses = ["1=1"]
    params: List[Any] = []

    if category and category != "ALL":
        clauses.append("(category = ? OR matched_services LIKE ?)")
        params.extend([category, f"%{category}%"])
    if region and region != "ALL":
        clauses.append("region = ?")
        params.append(region)
    if platform and platform != "ALL":
        clauses.append("source_platform = ?")
        params.append(platform)
    if status and status != "ALL":
        clauses.append("status = ?")
        params.append(status)
    if min_score > 0:
        clauses.append("relevance_score >= ?")
        params.append(int(min_score))
    if date_from:
        clauses.append("discovered_at >= ?")
        params.append(f"{date_from.strip()}T00:00:00Z")
    if date_to:
        clauses.append("discovered_at <= ?")
        params.append(f"{date_to.strip()}T23:59:59Z")
    if has_poc == "YES":
        clauses.append("(poc_phone != '' OR poc_email != '' OR poc_name != '')")
    if search_query:
        q = f"%{search_query.strip()}%"
        clauses.append(
            "(title LIKE ? OR snippet LIKE ? OR poc_company LIKE ? OR poc_name LIKE ? "
            "OR poc_email LIKE ? OR poc_phone LIKE ? OR poc_location LIKE ? OR ai_summary LIKE ?)"
        )
        params.extend([q, q, q, q, q, q, q, q])

    where_sql = " AND ".join(clauses)
    sql = f"""
        SELECT * FROM leads
        WHERE {where_sql}
        ORDER BY discovered_at DESC, relevance_score DESC
        LIMIT ?
    """
    params.append(int(limit))

    with _db_lock:
        session = UnifiedDBSession()
        try:
            rows = session.execute_fetchall(sql, tuple(params))
            out = []
            for d in rows:
                try:
                    d["matched_services"] = json.loads(d.get("matched_services") or "[]")
                except Exception:
                    d["matched_services"] = [d.get("category", "Energy Audit")]
                out.append(d)
            return out
        finally:
            session.close()


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            d = session.execute_fetchone(
                "SELECT * FROM leads WHERE id = ?", (int(lead_id),)
            )
            if not d:
                return None
            try:
                d["matched_services"] = json.loads(d.get("matched_services") or "[]")
            except Exception:
                d["matched_services"] = [d.get("category", "Energy Audit")]
            return d
        finally:
            session.close()


def get_dashboard_stats() -> Dict[str, Any]:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            total = int(
                (session.execute_fetchone("SELECT COUNT(*) as c FROM leads") or {}).get("c", 0)
            )
            high_intent = int(
                (
                    session.execute_fetchone(
                        "SELECT COUNT(*) as c FROM leads WHERE relevance_score >= 75"
                    )
                    or {}
                ).get("c", 0)
            )
            new_leads = int(
                (
                    session.execute_fetchone(
                        "SELECT COUNT(*) as c FROM leads WHERE status = 'New'"
                    )
                    or {}
                ).get("c", 0)
            )
            with_poc = int(
                (
                    session.execute_fetchone(
                        "SELECT COUNT(*) as c FROM leads WHERE poc_email != '' OR poc_phone != '' OR poc_name != ''"
                    )
                    or {}
                ).get("c", 0)
            )
            alerts_sent = int(
                (
                    session.execute_fetchone(
                        "SELECT COUNT(*) as c FROM notification_logs WHERE status = 'sent'"
                    )
                    or {}
                ).get("c", 0)
            )
            dup_row = session.execute_fetchone(
                "SELECT COALESCE(SUM(duplicates_skipped), 0) as d FROM scan_logs"
            )
            duplicates_blocked = int((dup_row or {}).get("d", 0))

            by_category = {}
            for row in session.execute_fetchall(
                "SELECT category, COUNT(*) as cnt FROM leads GROUP BY category"
            ):
                by_category[row["category"]] = int(row["cnt"])

            by_region = {}
            for row in session.execute_fetchall(
                "SELECT region, COUNT(*) as cnt FROM leads GROUP BY region"
            ):
                by_region[row["region"]] = int(row["cnt"])

            last_scan = session.execute_fetchone(
                "SELECT * FROM scan_logs ORDER BY id DESC LIMIT 1"
            )

            return {
                "total_leads": total,
                "high_intent_leads": high_intent,
                "new_leads": new_leads,
                "leads_with_poc": with_poc,
                "alerts_sent": alerts_sent,
                "duplicates_blocked": duplicates_blocked,
                "by_category": by_category,
                "by_region": by_region,
                "last_scan": last_scan,
                "db_status": get_db_status(),
            }
        finally:
            session.close()


def log_scan_start(trigger_type: str) -> int:
    now = utc_now_iso()
    with _db_lock:
        session = UnifiedDBSession()
        try:
            _, new_id = session.execute_write(
                "INSERT INTO scan_logs (trigger_type, started_at, status) VALUES (?, ?, 'running')",
                (trigger_type, now),
                return_id=True,
            )
            return int(new_id or 0)
        finally:
            session.close()


def log_scan_complete(
    scan_id: int,
    status: str,
    queries_run: int,
    raw_items_found: int,
    new_leads_saved: int,
    notifications_sent: int,
    details: str = "",
    duplicates_skipped: int = 0,
) -> None:
    now = utc_now_iso()
    with _db_lock:
        session = UnifiedDBSession()
        try:
            session.execute_write(
                """
                UPDATE scan_logs
                SET completed_at = ?, status = ?, queries_run = ?,
                    raw_items_found = ?, duplicates_skipped = ?,
                    new_leads_saved = ?, notifications_sent = ?, details = ?
                WHERE id = ?
                """,
                (
                    now,
                    status,
                    int(queries_run),
                    int(raw_items_found),
                    int(duplicates_skipped),
                    int(new_leads_saved),
                    int(notifications_sent),
                    details[:1000],
                    int(scan_id),
                ),
            )
        finally:
            session.close()


def log_notification(
    lead_id: Optional[int],
    channel: str,
    recipient: str,
    status: str,
    message_preview: str,
    error_detail: str = "",
) -> None:
    now = utc_now_iso()
    with _db_lock:
        session = UnifiedDBSession()
        try:
            session.execute_write(
                """
                INSERT INTO notification_logs (
                    lead_id, channel, recipient, status, message_preview, error_detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lead_id,
                    channel,
                    recipient,
                    status,
                    message_preview[:500],
                    error_detail[:500],
                    now,
                ),
            )
        finally:
            session.close()


def get_recent_logs(limit: int = 30) -> Dict[str, List[Dict[str, Any]]]:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            scans = session.execute_fetchall(
                "SELECT * FROM scan_logs ORDER BY id DESC LIMIT ?", (int(limit),)
            )
            notifications = session.execute_fetchall(
                "SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?", (int(limit),)
            )
            return {"scans": scans, "notifications": notifications}
        finally:
            session.close()


def seed_initial_leads_if_empty() -> None:
    with _db_lock:
        session = UnifiedDBSession()
        try:
            row = session.execute_fetchone("SELECT COUNT(*) as c FROM leads")
            if row and int(row["c"]) > 0:
                return
        finally:
            session.close()

    samples = [
        {
            "title": "RFP: ASHRAE Level 2 Energy Audit & BMS Optimization for Commercial Towers in Dubai Marina",
            "snippet": (
                "We are inviting qualified energy consultancy firms and ESCOs in the UAE to submit proposals "
                "for an ASHRAE Level 2 Energy Audit and Honeywell/Niagara BMS chiller plant optimization across "
                "3 commercial towers in Dubai Marina. Interested vendors please share company profile and ISO 50001 "
                "credentials to Eng. Tariq Al-Mansoori (Head of Facilities Management, Gulf Horizon Properties) at "
                "procurement@gulfhorizon-uae.ae or WhatsApp +971 50 482 9104 before next Thursday."
            ),
            "url": "https://www.linkedin.com/posts/tariq-almansoori-fm_rfp-energyaudit-bms-dubai-esco-activity-725101",
            "source_platform": "LinkedIn",
            "category": "Energy Audit",
            "matched_services": ["Energy Audit", "BMS"],
            "region": "UAE",
            "relevance_score": 94,
            "urgency": "High",
            "is_genuine_enquiry": True,
            "ai_summary": (
                "Direct RFP from Gulf Horizon Properties in Dubai seeking ASHRAE Level 2 Energy Audit and "
                "BMS chiller plant optimization across 3 towers in Dubai Marina."
            ),
            "poc_name": "Eng. Tariq Al-Mansoori",
            "poc_role": "Head of Facilities Management",
            "poc_company": "Gulf Horizon Properties",
            "poc_email": "procurement@gulfhorizon-uae.ae",
            "poc_phone": "+971 50 482 9104",
            "poc_linkedin": "https://www.linkedin.com/in/tariq-almansoori-fm",
            "poc_location": "Dubai, UAE",
            "suggested_pitch": (
                "Dear Eng. Tariq, SETS (www.sets4us.com) specializes in ASHRAE Level 2 Energy Audits and "
                "BMS Chiller Plant Optimization across the UAE. We would be glad to share our technical profile "
                "and case studies for your 3 commercial towers in Dubai Marina."
            ),
            "analyzed_by": "AI Watcher Seed",
        },
        {
            "title": "Seeking ESG Reporting & GHG Scope 1-3 Consultant for Listed Manufacturing Group in Riyadh, KSA",
            "snippet": (
                "Looking for an experienced Sustainability & ESG Advisory partner in Saudi Arabia (Riyadh/Dammam) "
                "to support our FY2026 Sustainability Report aligned with GRI Standards, Tadawul ESG guidelines, "
                "and Scope 1, 2 & 3 GHG inventory verification. Reach out to Sarah Al-Qahtani, Sustainability Lead "
                "at Najd Industrial Holdings via s.alqahtani@najdholding.sa or +966 55 319 8820."
            ),
            "url": "https://www.linkedin.com/posts/sarah-alqahtani-esg_esgreporting-sustainability-ksa-riyadh-gri-activity-725102",
            "source_platform": "LinkedIn",
            "category": "ESG Reporting",
            "matched_services": ["ESG Reporting", "Sustainability Audit"],
            "region": "KSA",
            "relevance_score": 91,
            "urgency": "High",
            "is_genuine_enquiry": True,
            "ai_summary": (
                "Active requirement in Riyadh, KSA for an ESG Reporting & Carbon Accounting consultant to prepare "
                "a Tadawul/GRI-aligned Sustainability Report and Scope 1-3 GHG Inventory."
            ),
            "poc_name": "Sarah Al-Qahtani",
            "poc_role": "Sustainability Lead",
            "poc_company": "Najd Industrial Holdings",
            "poc_email": "s.alqahtani@najdholding.sa",
            "poc_phone": "+966 55 319 8820",
            "poc_linkedin": "https://www.linkedin.com/in/sarah-alqahtani-esg",
            "poc_location": "Riyadh, KSA",
            "suggested_pitch": (
                "Hello Sarah, SETS (www.sets4us.com) delivers end-to-end GRI & Tadawul-compliant ESG Reporting "
                "and Scope 1, 2 & 3 GHG inventories for industrial groups in KSA. We would love to schedule a "
                "discovery call this week."
            ),
            "analyzed_by": "AI Watcher Seed",
        },
        {
            "title": "Vendor Enquiry: Central Monitoring System (CMS) & IoT Energy Metering for Multi-Site Retail in Mumbai & Bengaluru",
            "snippet": (
                "We are evaluating vendors for deploying a Central Monitoring System (CMS) and cloud EMS integrated "
                "with existing BACnet BMS and smart energy meters across 18 retail malls in Mumbai, Pune, and Bengaluru. "
                "Vendors with proven BMS/CMS integration capabilities please contact Rajesh Nair (VP Engineering, "
                "Vanguard Retail Infra) at rajesh.nair@vanguardinfra.in / +91 98204 51290."
            ),
            "url": "https://www.linkedin.com/posts/rajesh-nair-infra_cms-bms-ems-iot-india-energyefficiency-activity-725103",
            "source_platform": "LinkedIn",
            "category": "CMS",
            "matched_services": ["CMS", "BMS"],
            "region": "India",
            "relevance_score": 89,
            "urgency": "High",
            "is_genuine_enquiry": True,
            "ai_summary": (
                "Multi-site CMS & IoT Energy Management System enquiry covering 18 retail properties in Mumbai, "
                "Pune, and Bengaluru requiring BACnet BMS integration."
            ),
            "poc_name": "Rajesh Nair",
            "poc_role": "VP Engineering",
            "poc_company": "Vanguard Retail Infra",
            "poc_email": "rajesh.nair@vanguardinfra.in",
            "poc_phone": "+91 98204 51290",
            "poc_linkedin": "https://www.linkedin.com/in/rajesh-nair-infra",
            "poc_location": "Mumbai & Bengaluru, India",
            "suggested_pitch": (
                "Dear Rajesh, SETS (www.sets4us.com) has extensive experience designing and integrating Central "
                "Monitoring Systems (CMS), EMS, and BACnet BMS across commercial portfolios in India. Can we "
                "connect to discuss your 18-site rollout?"
            ),
            "analyzed_by": "AI Watcher Seed",
        },
        {
            "title": "Tender Notice: Estidama & Sustainability Audit Consultancy for Logistics Park in Abu Dhabi (KEZAD)",
            "snippet": (
                "Expression of Interest (EOI) invited for Sustainability Audit, LEED O+M / Estidama Pearl rating "
                "compliance, and solar/HVAC decarbonization roadmap for a 45,000 sqm cold-chain logistics facility "
                "in KEZAD, Abu Dhabi. Contact Contracts Team at tenders@kezadlogistics-ae.com."
            ),
            "url": "https://news.google.com/articles/kezad-sustainability-audit-eoi-abudhabi",
            "source_platform": "Web / Tenders",
            "category": "Sustainability Audit",
            "matched_services": ["Sustainability Audit", "Energy Audit"],
            "region": "UAE",
            "relevance_score": 86,
            "urgency": "Medium",
            "is_genuine_enquiry": True,
            "ai_summary": (
                "EOI for Sustainability Audit, Estidama/LEED O+M certification, and decarbonization study for "
                "a 45,000 sqm logistics facility in Abu Dhabi."
            ),
            "poc_name": "Contracts & Procurement Team",
            "poc_role": "Tender Committee",
            "poc_company": "KEZAD Cold-Chain Logistics",
            "poc_email": "tenders@kezadlogistics-ae.com",
            "poc_phone": "",
            "poc_linkedin": "",
            "poc_location": "Abu Dhabi, UAE",
            "suggested_pitch": (
                "Dear Contracts Team, please find our Expression of Interest from SETS (www.sets4us.com) for the "
                "Sustainability Audit, Estidama/LEED compliance, and decarbonization roadmap at KEZAD."
            ),
            "analyzed_by": "AI Watcher Seed",
        },
    ]

    for s in samples:
        insert_lead(s, check_duplicates=False)
