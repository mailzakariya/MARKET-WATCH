"""
SETS AI Lead Watcher - Main 64-Bit Windows Application & Secure Server (www.sets4us.com)
Provides:
1. Hardened Local REST API with Windows DPAPI secret encryption, rate limiting & security headers
2. Native Desktop GUI Control Window (with SETS Logo Icon) + Automatic Full Dashboard App Window
3. PostgreSQL & Anti-Duplication Engine + Open-Source WhatsApp Bridge with User Profile Isolation
"""

import argparse
import json
import mimetypes
import os
import platform
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from watcher.buildings import ALL_MUNICIPALITIES
from watcher.config import COMPANY_PROFILE
from watcher.database import (
    DB_DIR,
    add_team_contact,
    delete_building_permit,
    delete_lead,
    delete_search_area,
    delete_team_contact,
    get_active_username,
    get_dashboard_stats,
    get_db_status,
    get_lead_by_id,
    get_recent_logs,
    get_settings,
    init_db,
    insert_building_permit,
    list_building_permits,
    list_leads,
    list_search_areas,
    list_team_contacts,
    list_users,
    login_or_create_user,
    save_search_area,
    set_active_username,
    test_postgres_connection,
    update_lead_status,
    update_settings,
    update_team_contact,
)
from watcher.engine import watcher_engine
from watcher.notifier import (
    format_whatsapp_message,
    send_email_notification,
    send_whatsapp_notification,
)
from watcher.security import mask_settings_for_client, rate_limiter


def get_resource_base_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_resource_base_dir()
STATIC_DIR = os.path.join(BASE_DIR, "static")
ICON_PATH = os.path.join(BASE_DIR, "assets", "sets_logo.ico")


def build_sample_test_lead() -> Dict[str, Any]:
    return {
        "id": None,
        "title": "TEST ALERT: ASHRAE Level 2 Energy Audit & BMS Upgrade Enquiry",
        "snippet": (
            "This is a test notification from your SETS AI Lead Watcher (www.sets4us.com). "
            "When a live Energy Audit, Sustainability Audit, BMS, CMS, or ESG Reporting enquiry "
            "is detected in UAE, KSA, or India, your team will receive this structured alert."
        ),
        "url": "https://www.sets4us.com",
        "source_platform": "LinkedIn",
        "category": "Energy Audit",
        "matched_services": ["Energy Audit", "BMS", "ESG Reporting"],
        "region": "India",
        "relevance_score": 95,
        "urgency": "High",
        "ai_summary": "Test verification alert confirming SETS AI Watcher notification pipeline.",
        "poc_name": "Eng. Khalid Al-Nuaimi",
        "poc_role": "Director of Engineering & Sustainability",
        "poc_company": "Emirates Commercial Towers LLC",
        "poc_email": "khalid.nuaimi@example-uae.ae",
        "poc_phone": "+971 50 123 4567",
        "poc_linkedin": "https://www.linkedin.com/company/sets4us",
        "poc_location": "Mumbai / Dubai",
        "suggested_pitch": (
            "Dear Eng. Khalid, SETS (www.sets4us.com) would be delighted to support your "
            "ASHRAE Level 2 Energy Audit and BMS upgrade."
        ),
    }


class WatcherRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _apply_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self';",
        )
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")

    def _check_rate_limit(self) -> bool:
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        if not rate_limiter.is_allowed(client_ip):
            self._send_json(
                {"ok": False, "error": "Too many requests. Rate limit exceeded."},
                status=429,
            )
            return False
        return True

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._apply_security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 2_000_000:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _serve_static(self, rel_path: str) -> None:
        safe_rel = os.path.normpath(rel_path).lstrip("\\/")
        full_path = os.path.abspath(os.path.join(STATIC_DIR, safe_rel))
        if not full_path.startswith(os.path.abspath(STATIC_DIR)) or not os.path.isfile(full_path):
            self._send_json({"error": "Not found"}, status=404)
            return

        ctype, _ = mimetypes.guess_type(full_path)
        if not ctype:
            ctype = "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"

        with open(full_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self._apply_security_headers()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _get_username(self, qs: Optional[Dict[str, List[str]]] = None, body: Optional[Dict[str, Any]] = None) -> str:
        u = ""
        if qs:
            u = (qs.get("username", [""])[0] or "").strip()
        if not u and body:
            u = (body.get("username") or "").strip()
        if not u:
            u = (self.headers.get("X-Sets-Username") or "").strip()
        if not u:
            u = get_active_username()
        return u

    def do_GET(self) -> None:
        if not self._check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_static("index.html")
            return
        if path in ("/favicon.ico", "/sets_logo.ico"):
            self._serve_static("sets_logo.ico")
            return
        if path in ("/styles.css", "/app.js", "/mobile_engine.js"):
            self._serve_static(path.lstrip("/"))
            return
        if path.startswith("/static/"):
            self._serve_static(path[len("/static/") :])
            return

        if path == "/api/auth/current":
            self._send_json(
                {
                    "ok": True,
                    "active_user": get_active_username(),
                    "users": list_users(),
                }
            )
            return

        if path == "/api/auth/users":
            self._send_json({"ok": True, "users": list_users()})
            return

        if path == "/api/areas":
            uname = self._get_username(qs)
            self._send_json(
                {
                    "ok": True,
                    "areas": list_search_areas(username=uname),
                    "active_user": uname,
                }
            )
            return

        if path == "/api/overview":
            uname = self._get_username(qs)
            self._send_json(
                {
                    "company": COMPANY_PROFILE,
                    "stats": get_dashboard_stats(username=uname),
                    "watcher": watcher_engine.get_status(),
                    "active_user": uname,
                    "security": {
                        "encryption": "Windows 64-Bit DPAPI + PBKDF2-SHA256 Active",
                        "arch": platform.machine(),
                    },
                }
            )
            return

        if path == "/api/leads":
            uname = self._get_username(qs)
            category = qs.get("category", ["ALL"])[0]
            region = qs.get("region", ["ALL"])[0]
            platform_f = qs.get("platform", ["ALL"])[0]
            status = qs.get("status", ["ALL"])[0]
            min_score = int(qs.get("min_score", ["0"])[0] or 0)
            q = qs.get("q", [""])[0]
            date_from = qs.get("date_from", [""])[0]
            date_to = qs.get("date_to", [""])[0]
            has_poc = qs.get("has_poc", [""])[0]
            limit = int(qs.get("limit", ["250"])[0] or 250)
            leads = list_leads(
                category=category,
                region=region,
                platform=platform_f,
                status=status,
                min_score=min_score,
                search_query=q,
                date_from=date_from,
                date_to=date_to,
                has_poc=has_poc,
                limit=limit,
                username=uname,
            )
            self._send_json({"leads": leads, "count": len(leads), "active_user": uname})
            return

        if path == "/api/buildings":
            uname = self._get_username(qs)
            country = qs.get("country", ["ALL"])[0]
            municipality = qs.get("municipality", ["ALL"])[0]
            project_type = qs.get("project_type", ["ALL"])[0]
            q = qs.get("q", [""])[0]
            permits = list_building_permits(
                country=country,
                municipality=municipality,
                project_type=project_type,
                search_query=q,
                username=uname,
            )
            self._send_json(
                {
                    "permits": permits,
                    "count": len(permits),
                    "municipalities": list(ALL_MUNICIPALITIES.keys()),
                    "active_user": uname,
                }
            )
            return

        if path == "/api/contacts":
            uname = self._get_username(qs)
            self._send_json(
                {
                    "contacts": list_team_contacts(active_only=False, username=uname),
                    "active_user": uname,
                }
            )
            return

        if path == "/api/postgres/status":
            self._send_json(get_db_status())
            return

        if path == "/api/settings":
            uname = self._get_username(qs)
            raw_settings = get_settings(username=uname)
            self._send_json(
                {
                    "settings": mask_settings_for_client(raw_settings),
                    "db_status": get_db_status(),
                    "active_user": uname,
                }
            )
            return

        if path == "/api/logs":
            self._send_json(get_recent_logs(limit=35))
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def do_POST(self) -> None:
        if not self._check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/search/live":
            keyword = (body.get("keyword") or "").strip()
            region = (body.get("region") or "ALL").strip()
            category = (body.get("category") or "Energy Audit").strip()
            if not keyword:
                self._send_json(
                    {"ok": False, "error": "Please enter a keyword to search on LinkedIn & Internet."},
                    status=400,
                )
                return
            res = watcher_engine.run_live_keyword_search(
                keyword=keyword, region=region, category=category
            )
            self._send_json(res)
            return

        if path == "/api/buildings/scan":
            country = (body.get("country") or "ALL").strip()
            municipality = (body.get("municipality") or "ALL").strip()
            res = watcher_engine.run_buildings_scan(
                country=country, municipality=municipality
            )
            self._send_json(res)
            return

        if path == "/api/buildings/add":
            pid, dup = insert_building_permit(body, check_duplicates=True)
            self._send_json(
                {
                    "ok": pid is not None,
                    "id": pid,
                    "duplicate_reason": dup,
                }
            )
            return

        if path == "/api/buildings/delete":
            pid = int(body.get("id") or 0)
            ok = delete_building_permit(pid)
            self._send_json({"ok": ok})
            return

        if path == "/api/scan/trigger":
            if watcher_engine.is_scanning:
                self._send_json(
                    {
                        "ok": False,
                        "message": "Scan already running.",
                        "watcher": watcher_engine.get_status(),
                    }
                )
                return
            run_sync = bool(body.get("sync", False))
            if run_sync:
                res = watcher_engine.run_scan(trigger_type="manual")
                self._send_json(res)
            else:
                threading.Thread(
                    target=watcher_engine.run_scan,
                    kwargs={"trigger_type": "manual"},
                    daemon=True,
                ).start()
                self._send_json(
                    {
                        "ok": True,
                        "message": "Internet & social media scan started (with duplicate filtering).",
                        "watcher": watcher_engine.get_status(),
                    }
                )
            return

        if path == "/api/analyze":
            title = (body.get("title") or "").strip()
            snippet = (body.get("snippet") or "").strip()
            url = (body.get("url") or "").strip()
            platform_f = (body.get("source_platform") or "LinkedIn").strip()
            save_to_db = bool(body.get("save_to_db", True))
            send_notifications = bool(body.get("send_notifications", False))

            if not snippet and not title:
                self._send_json(
                    {"ok": False, "error": "Please provide enquiry text or title to analyze."},
                    status=400,
                )
                return

            res = watcher_engine.analyze_custom_post(
                title=title,
                snippet=snippet,
                url=url,
                source_platform=platform_f,
                save_to_db=save_to_db,
                send_notifications=send_notifications,
            )
            self._send_json(res)
            return

        if path == "/api/leads/status":
            lead_id = int(body.get("lead_id") or 0)
            new_status = (body.get("status") or "New").strip()
            ok = update_lead_status(lead_id, new_status)
            self._send_json({"ok": ok})
            return

        if path == "/api/leads/delete":
            lead_id = int(body.get("lead_id") or 0)
            ok = delete_lead(lead_id)
            self._send_json({"ok": ok})
            return

        if path == "/api/leads/notify":
            lead_id = int(body.get("lead_id") or 0)
            channel = (body.get("channel") or "both").lower()
            lead = get_lead_by_id(lead_id)
            if not lead:
                self._send_json({"ok": False, "error": "Lead not found"}, status=404)
                return
            settings = get_settings()
            out: Dict[str, Any] = {"ok": True, "results": {}}
            if channel in ("email", "both"):
                ok_e, msg_e = send_email_notification(lead, settings)
                out["results"]["email"] = {"ok": ok_e, "detail": msg_e}
            if channel in ("whatsapp", "both"):
                ok_w, msg_w = send_whatsapp_notification(lead, settings)
                out["results"]["whatsapp"] = {"ok": ok_w, "detail": msg_w}
            out["whatsapp_share_text"] = format_whatsapp_message(lead)
            self._send_json(out)
            return

        if path == "/api/auth/login":
            uname = (body.get("username") or "").strip()
            dname = (body.get("display_name") or uname).strip()
            res = login_or_create_user(uname, dname)
            self._send_json(res)
            return

        if path == "/api/auth/switch":
            uname = (body.get("username") or "").strip()
            set_active_username(uname)
            self._send_json({"ok": True, "active_user": uname})
            return

        if path == "/api/areas/save":
            uname = self._get_username(None, body)
            res = save_search_area(body, username=uname)
            self._send_json(res)
            return

        if path == "/api/areas/delete":
            uname = self._get_username(None, body)
            aid = int(body.get("id") or 0)
            ok = delete_search_area(aid, username=uname)
            self._send_json({"ok": ok, "areas": list_search_areas(username=uname)})
            return

        if path == "/api/contacts/add":
            uname = self._get_username(None, body)
            res = add_team_contact(body, username=uname)
            self._send_json(
                {
                    "ok": bool(res.get("ok")),
                    "is_duplicate": bool(res.get("is_duplicate")),
                    "error": res.get("error", ""),
                    "result": res,
                    "contacts": list_team_contacts(username=uname),
                }
            )
            return

        if path == "/api/contacts/update":
            uname = self._get_username(None, body)
            cid = int(body.get("id") or 0)
            res = update_team_contact(cid, body, username=uname)
            self._send_json(
                {
                    "ok": bool(res.get("ok")),
                    "is_duplicate": bool(res.get("is_duplicate")),
                    "error": res.get("error", ""),
                    "result": res,
                    "contacts": list_team_contacts(username=uname),
                }
            )
            return

        if path == "/api/contacts/delete":
            uname = self._get_username(None, body)
            cid = int(body.get("id") or 0)
            ok = delete_team_contact(cid, username=uname)
            self._send_json({"ok": ok, "contacts": list_team_contacts(username=uname)})
            return

        if path == "/api/contacts/test":
            channel = (body.get("channel") or "whatsapp").lower()
            target = (body.get("target") or "").strip()
            uname = self._get_username(None, body)
            settings = get_settings(username=uname)
            sample = build_sample_test_lead()
            if channel == "whatsapp":
                ok, detail = send_whatsapp_notification(
                    sample, settings, override_recipients=[target] if target else None
                )
            else:
                ok, detail = send_email_notification(
                    sample, settings, override_recipients=[target] if target else None
                )
            self._send_json({"ok": ok, "detail": detail})
            return

        if path == "/api/postgres/test":
            res = test_postgres_connection(body)
            if res.get("ok"):
                update_settings(body)
            self._send_json(res)
            return

        if path == "/api/settings":
            uname = self._get_username(None, body)
            updated = update_settings(body, username=uname)
            self._send_json(
                {
                    "ok": True,
                    "settings": mask_settings_for_client(updated),
                    "db_status": get_db_status(),
                    "active_user": uname,
                }
            )
            return

        if path == "/api/test-notification":
            channel = (body.get("channel") or "whatsapp").lower()
            settings = get_settings()
            if isinstance(body.get("settings"), dict):
                for k, v in body["settings"].items():
                    if v != "••••••••••••••••":
                        settings[k] = v

            sample_lead = build_sample_test_lead()
            if channel == "email":
                ok, detail = send_email_notification(sample_lead, settings)
                self._send_json({"ok": ok, "detail": detail})
            else:
                ok, detail = send_whatsapp_notification(sample_lead, settings)
                self._send_json({"ok": ok, "detail": detail})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def open_native_dashboard_window(url: str) -> None:
    """
    Launch the full interactive dashboard in a dedicated native desktop window
    (Edge/Chrome --app mode on Windows 64-bit, with default browser fallback).
    """
    if os.name == "nt":
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for ep in edge_paths:
            if os.path.isfile(ep):
                try:
                    subprocess.Popen([ep, f"--app={url}", "--window-size=1420,900"])
                    return
                except Exception:
                    pass
    webbrowser.open(url)


def launch_desktop_control_gui(server: ThreadingHTTPServer, url: str) -> None:
    """
    Opens the native Windows 64-bit SETS Desktop Control Center GUI (with SETS Logo Icon)
    and automatically launches the full dashboard window.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        open_native_dashboard_window(url)
        server.serve_forever()
        return

    root = tk.Tk()
    root.title("SETS AI Lead Watcher (64-Bit) | www.sets4us.com")
    root.geometry("640x430")
    root.configure(bg="#0b1120")
    root.resizable(False, False)

    if os.path.isfile(ICON_PATH):
        try:
            root.iconbitmap(ICON_PATH)
        except Exception:
            pass

    # Header Frame
    header = tk.Frame(root, bg="#064e3b", padx=20, pady=16)
    header.pack(fill="x")
    tk.Label(
        header,
        text="SETS AI Lead Watcher • 64-Bit Windows Edition",
        font=("Segoe UI", 14, "bold"),
        fg="#f8fafc",
        bg="#064e3b",
    ).pack(anchor="w")
    tk.Label(
        header,
        text="www.sets4us.com | Energy Audit • Sustainability • BMS • CMS • ESG Reporting",
        font=("Segoe UI", 9),
        fg="#a7f3d0",
        bg="#064e3b",
    ).pack(anchor="w", pady=(2, 0))

    # Status Body
    body = tk.Frame(root, bg="#0b1120", padx=22, pady=16)
    body.pack(fill="both", expand=True)

    status_var = tk.StringVar(value="● AI Watcher Engine & Local Secure Server Running")
    db_var = tk.StringVar(value="Database: Checking PostgreSQL & Local Cache...")
    stats_var = tk.StringVar(value="Leads Stored: 0 | User Profile: Multi-User Isolated")
    sec_var = tk.StringVar(
        value="Security: Windows 64-Bit DPAPI Credential Encryption + CSP + Rate Limiter Active"
    )

    tk.Label(
        body,
        textvariable=status_var,
        font=("Segoe UI", 10, "bold"),
        fg="#34d399",
        bg="#0b1120",
    ).pack(anchor="w", pady=(0, 6))
    tk.Label(
        body, textvariable=db_var, font=("Segoe UI", 9), fg="#cbd5e1", bg="#0b1120"
    ).pack(anchor="w", pady=2)
    tk.Label(
        body, textvariable=stats_var, font=("Segoe UI", 9), fg="#cbd5e1", bg="#0b1120"
    ).pack(anchor="w", pady=2)
    tk.Label(
        body, textvariable=sec_var, font=("Segoe UI", 9), fg="#38bdf8", bg="#0b1120"
    ).pack(anchor="w", pady=(2, 14))

    def refresh_gui_stats() -> None:
        def _worker() -> None:
            try:
                active_user = get_active_username() or "Default User"
                st = get_dashboard_stats(username=active_user)
                w = watcher_engine.get_status()
                db_info = st.get("db_status", {})
                status_txt = (
                    f"● Watcher Status: {'Scanning (' + w.get('current_stage', '') + ')' if w.get('is_scanning') else 'Active & Monitoring (UAE, KSA, India)'}"
                )
                db_txt = f"Database Engine: {db_info.get('engine', 'PostgreSQL')}"
                stats_txt = (
                    f"User Profile: {active_user}  |  Enquiries: {st.get('total_leads', 0)}  |  Duplicates Filtered: {st.get('duplicates_blocked', 0)}"
                )
                root.after(
                    0,
                    lambda: (
                        status_var.set(status_txt),
                        db_var.set(db_txt),
                        stats_var.set(stats_txt),
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()
        root.after(5000, refresh_gui_stats)

    # Action Buttons Grid
    btn_frame = tk.Frame(body, bg="#0b1120")
    btn_frame.pack(fill="x", pady=8)

    def on_open_dashboard() -> None:
        open_native_dashboard_window(url)

    def on_scan_now() -> None:
        threading.Thread(
            target=watcher_engine.run_scan, kwargs={"trigger_type": "manual"}, daemon=True
        ).start()
        status_var.set("● Triggered Live Internet & Social Media Scan...")

    def on_open_wa_bridge() -> None:
        exe_dir = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__))
        )
        bat_path = os.path.join(exe_dir, "start_whatsapp_bridge.bat")
        if os.path.isfile(bat_path):
            subprocess.Popen(["cmd.exe", "/c", "start", "", bat_path], cwd=exe_dir)
        else:
            webbrowser.open("http://127.0.0.1:3001")

    tk.Button(
        btn_frame,
        text="🖥️ Open Full Dashboard GUI",
        command=on_open_dashboard,
        bg="#10b981",
        fg="#052e16",
        font=("Segoe UI", 10, "bold"),
        padx=14,
        pady=8,
        relief="flat",
        cursor="hand2",
    ).grid(row=0, column=0, padx=(0, 10), pady=6, sticky="ew")

    tk.Button(
        btn_frame,
        text="🔍 Scan Internet Now",
        command=on_scan_now,
        bg="#1e293b",
        fg="#f8fafc",
        font=("Segoe UI", 10, "bold"),
        padx=14,
        pady=8,
        relief="flat",
        cursor="hand2",
    ).grid(row=0, column=1, padx=10, pady=6, sticky="ew")

    tk.Button(
        btn_frame,
        text="💬 Start Open-Source WhatsApp Bridge",
        command=on_open_wa_bridge,
        bg="#065f46",
        fg="#ecfdf5",
        font=("Segoe UI", 9, "bold"),
        padx=14,
        pady=8,
        relief="flat",
        cursor="hand2",
    ).grid(row=1, column=0, columnspan=2, pady=6, sticky="ew")

    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    tk.Label(
        body,
        text=f"Data Directory: {DB_DIR}   |   Local URL: {url}",
        font=("Segoe UI", 8),
        fg="#64748b",
        bg="#0b1120",
    ).pack(anchor="w", pady=(12, 0))

    def on_close() -> None:
        if messagebox.askokcancel(
            "Exit SETS AI Lead Watcher",
            "Stop the background AI Watcher and close the application?",
        ):
            watcher_engine.stop_background_loop()
            threading.Thread(target=server.shutdown, daemon=True).start()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Automatically launch the full interactive Dashboard window on startup
    root.after(600, lambda: open_native_dashboard_window(url))
    root.after(500, refresh_gui_stats)
    root.mainloop()


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    headless: bool = False,
) -> None:
    init_db()
    watcher_engine.start_background_loop()
    server = ThreadingHTTPServer((host, port), WatcherRequestHandler)
    url = f"http://{host}:{port}"

    if headless:
        if open_browser:
            threading.Timer(1.0, lambda: open_native_dashboard_window(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            watcher_engine.stop_background_loop()
            server.server_close()
    else:
        server_thread = threading.Thread(
            target=server.serve_forever, name="SETSHttpServer", daemon=True
        )
        server_thread.start()
        launch_desktop_control_gui(server, url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SETS AI Lead Watcher (64-Bit Windows)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--open", action="store_true", default=True, help="Open GUI automatically")
    parser.add_argument("--headless", action="store_true", help="Run without native control window")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, open_browser=args.open, headless=args.headless)
