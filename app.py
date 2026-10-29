"""
SETS AI Lead Watcher - Main Application Server (www.sets4us.com)
Provides the REST API, Static Dashboard Server, PostgreSQL & Team Contacts APIs,
and Background Watcher Daemon.
"""

import argparse
import json
import mimetypes
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from watcher.config import COMPANY_PROFILE
from watcher.database import (
    add_team_contact,
    delete_lead,
    delete_team_contact,
    get_dashboard_stats,
    get_db_status,
    get_lead_by_id,
    get_recent_logs,
    get_settings,
    init_db,
    list_leads,
    list_team_contacts,
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


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
        "poc_phone": "+91 81388 58961",
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

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
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
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_static("index.html")
            return
        if path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
            return

        if path == "/api/overview":
            self._send_json(
                {
                    "company": COMPANY_PROFILE,
                    "stats": get_dashboard_stats(),
                    "watcher": watcher_engine.get_status(),
                }
            )
            return

        if path == "/api/leads":
            category = qs.get("category", ["ALL"])[0]
            region = qs.get("region", ["ALL"])[0]
            platform = qs.get("platform", ["ALL"])[0]
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
                platform=platform,
                status=status,
                min_score=min_score,
                search_query=q,
                date_from=date_from,
                date_to=date_to,
                has_poc=has_poc,
                limit=limit,
            )
            self._send_json({"leads": leads, "count": len(leads)})
            return

        if path == "/api/contacts":
            self._send_json({"contacts": list_team_contacts(active_only=False)})
            return

        if path == "/api/postgres/status":
            self._send_json(get_db_status())
            return

        if path == "/api/settings":
            self._send_json({"settings": get_settings(), "db_status": get_db_status()})
            return

        if path == "/api/logs":
            self._send_json(get_recent_logs(limit=35))
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

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
            platform = (body.get("source_platform") or "LinkedIn").strip()
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
                source_platform=platform,
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

        # Team Contacts CRUD (Add, Edit, Delete numbers & emails)
        if path == "/api/contacts/add":
            res = add_team_contact(body)
            self._send_json({"ok": True, "result": res, "contacts": list_team_contacts()})
            return

        if path == "/api/contacts/update":
            cid = int(body.get("id") or 0)
            ok = update_team_contact(cid, body)
            self._send_json({"ok": ok, "contacts": list_team_contacts()})
            return

        if path == "/api/contacts/delete":
            cid = int(body.get("id") or 0)
            ok = delete_team_contact(cid)
            self._send_json({"ok": ok, "contacts": list_team_contacts()})
            return

        if path == "/api/contacts/test":
            channel = (body.get("channel") or "whatsapp").lower()
            target = (body.get("target") or "").strip()
            settings = get_settings()
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

        # PostgreSQL Connection Test & Save
        if path == "/api/postgres/test":
            res = test_postgres_connection(body)
            if res.get("ok"):
                update_settings(body)
            self._send_json(res)
            return

        if path == "/api/settings":
            updated = update_settings(body)
            self._send_json({"ok": True, "settings": updated, "db_status": get_db_status()})
            return

        if path == "/api/test-notification":
            channel = (body.get("channel") or "whatsapp").lower()
            settings = get_settings()
            if isinstance(body.get("settings"), dict):
                settings.update(body["settings"])

            sample_lead = build_sample_test_lead()
            if channel == "email":
                ok, detail = send_email_notification(sample_lead, settings)
                self._send_json({"ok": ok, "detail": detail})
            else:
                ok, detail = send_whatsapp_notification(sample_lead, settings)
                self._send_json({"ok": ok, "detail": detail})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = False) -> None:
    init_db()
    watcher_engine.start_background_loop()
    server = ThreadingHTTPServer((host, port), WatcherRequestHandler)
    url = f"http://{host}:{port}"
    print("=" * 72)
    print("  SETS AI Lead Watcher (www.sets4us.com)")
    print(f"  Dashboard URL     : {url}")
    print("  Default WhatsApp  : +918138858961 (Open-Source WhatsApp Bridge Ready)")
    print("  Database Engine   : PostgreSQL (Neon / Supabase / Local PG + Cache)")
    print("  Target Regions    : UAE, KSA, India")
    print("=" * 72)

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down SETS AI Lead Watcher...")
        watcher_engine.stop_background_loop()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SETS AI Lead Watcher Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--open", action="store_true", help="Open web browser automatically")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, open_browser=args.open)
