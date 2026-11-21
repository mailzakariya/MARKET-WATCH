"""
PostgreSQL administration helpers for SETS AI Lead Watcher.

Creates a dedicated, least-privilege login role for the application (default
'sets_app') that owns only the application database, so the app never has to
run with the 'postgres' superuser account.

This module has no import-time side effects (it is also bundled into the
Setup wizard) and only depends on the pure-Python pg8000 driver.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
from typing import Any, Dict, Tuple

DEFAULT_APP_ROLE = "sets_app"
_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_DB_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,62}$")
_RESERVED_ROLES = {"postgres", "public", "pg_monitor", "pg_read_all_data", "pg_write_all_data"}


def generate_app_password(length: int = 24) -> str:
    """Random password using only characters that need no quoting anywhere."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def scram_sha256_verifier(password: str, iterations: int = 4096) -> str:
    """
    Build the SCRAM-SHA-256 verifier PostgreSQL stores for a password, so the
    plain-text password is never sent in a CREATE/ALTER ROLE statement (and
    therefore can never end up in server statement logs).
    """
    salt = os.urandom(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def _friendly(exc: Exception) -> str:
    raw = str(exc)
    if "28P01" in raw or "password authentication failed" in raw:
        return "Password authentication failed for the administrator account."
    if "42501" in raw or "permission denied" in raw.lower() or "must have createrole" in raw.lower():
        return (
            "This administrator account is not allowed to create logins (CREATEROLE). "
            "Use the 'postgres' superuser, or keep using the account you entered."
        )
    if "timed out" in raw.lower() or "10061" in raw or "refused" in raw.lower() or "create a connection" in raw.lower():
        return "Could not reach the PostgreSQL server — is it installed and running?"
    m = re.search(r"'M': '([^']+)'", raw)
    return m.group(1) if m else raw[:200]


def _connect(params: Dict[str, Any], user: str, password: str, database: str):
    import pg8000.dbapi

    host = params.get("host") or "localhost"
    ssl_ctx = True if params.get("sslmode") in ("require", "verify-ca", "verify-full") else None
    conn = pg8000.dbapi.connect(
        host="127.0.0.1" if host == "localhost" else host,
        port=int(params.get("port") or 5432),
        database=database,
        user=user,
        password=password,
        timeout=8,
        ssl_context=ssl_ctx,
    )
    conn.autocommit = True
    return conn


def provision_app_login(
    params: Dict[str, Any],
    admin_user: str,
    admin_password: str,
    app_user: str = DEFAULT_APP_ROLE,
    app_password: str = "",
) -> Tuple[bool, str, str]:
    """
    Using an administrator account, create (or reset) a dedicated LOGIN role and
    make it the owner of the application database.

    params: host, port, dbname, sslmode
    Returns (ok, message, app_password). The password is generated when not given.
    """
    dbname = (params.get("dbname") or "sets_watcher").strip()
    app_user = (app_user or DEFAULT_APP_ROLE).strip().lower()
    if not _ROLE_RE.match(app_user) or app_user in _RESERVED_ROLES or app_user.startswith("pg_"):
        return False, f"Invalid login name {app_user!r}: use lowercase letters, digits and _ only.", ""
    if app_user == (admin_user or "").strip().lower():
        return False, "The application login must be different from the administrator account.", ""
    if not _DB_RE.match(dbname):
        return False, f"Invalid database name: {dbname!r}", ""
    app_password = app_password or generate_app_password()

    try:
        import pg8000.dbapi  # noqa: F401
    except ImportError:
        return False, "PostgreSQL driver (pg8000) is not available.", ""

    role_q = f'"{app_user}"'
    db_q = f'"{dbname}"'
    verifier = scram_sha256_verifier(app_password)

    # 1. Role + database ownership (server level)
    try:
        admin = _connect(params, admin_user, admin_password, "postgres")
    except Exception as exc:
        return False, _friendly(exc), ""
    try:
        cur = admin.cursor()
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
        role_existed = cur.fetchone() is not None
        verb = "ALTER" if role_existed else "CREATE"
        cur.execute(
            f"{verb} ROLE {role_q} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
            f"PASSWORD '{verifier}'"
        )
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone():
            cur.execute(f"ALTER DATABASE {db_q} OWNER TO {role_q}")
        else:
            cur.execute(f"CREATE DATABASE {db_q} OWNER {role_q}")
        # Only the app login (and superusers) may connect to the app database
        cur.execute(f"REVOKE CONNECT, TEMPORARY ON DATABASE {db_q} FROM PUBLIC")
        cur.execute(f"GRANT CONNECT, TEMPORARY ON DATABASE {db_q} TO {role_q}")
    except Exception as exc:
        return False, _friendly(exc), ""
    finally:
        try:
            admin.close()
        except Exception:
            pass

    # 2. Hand over existing tables/sequences created earlier by another account
    moved = 0
    try:
        adb = _connect(params, admin_user, admin_password, dbname)
        try:
            cur = adb.cursor()
            cur.execute(f"GRANT ALL ON SCHEMA public TO {role_q}")
            cur.execute(
                """
                SELECT c.relname, c.relkind
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
                  AND pg_get_userbyid(c.relowner) <> %s
                """,
                (app_user,),
            )
            kinds = {"r": "TABLE", "p": "TABLE", "v": "VIEW", "m": "MATERIALIZED VIEW", "S": "SEQUENCE"}
            rows = cur.fetchall()
            # Tables first; sequences owned by a table column follow the table automatically
            for relname, relkind in sorted(rows, key=lambda r: r[1] == "S"):
                try:
                    cur.execute(f'ALTER {kinds[relkind]} public."{relname}" OWNER TO {role_q}')
                    moved += 1
                except Exception:
                    pass
        finally:
            adb.close()
    except Exception as exc:
        return False, f"Login created, but could not transfer existing tables: {_friendly(exc)}", ""

    # 3. Prove the new login works and can create tables
    try:
        conn = _connect(params, app_user, app_password, dbname)
        try:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS _sets_login_check (id INTEGER)")
            cur.execute("DROP TABLE _sets_login_check")
        finally:
            conn.close()
    except Exception as exc:
        return False, f"Login '{app_user}' was created but could not connect: {_friendly(exc)}", ""

    action = "Reset password for" if role_existed else "Created"
    extra = f", took ownership of {moved} existing tables" if moved else ""
    return True, f"{action} database login '{app_user}' (owner of '{dbname}'{extra}).", app_password
