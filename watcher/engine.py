"""
Background Watcher Daemon & Scan Orchestrator for SETS (www.sets4us.com).
Continuously monitors internet & social media sources, runs AI analysis,
checks against existing database enquiries to prevent duplicates/similar results,
stores qualified leads, and dispatches Email & WhatsApp notifications.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from watcher.analyzer import analyze_item
from watcher.database import (
    check_duplicate_or_similar_lead,
    get_lead_by_id,
    get_settings,
    insert_lead,
    log_scan_complete,
    log_scan_start,
)
from watcher.notifier import notify_for_lead
from watcher.sources import run_multi_source_discovery


class WatcherEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.is_scanning: bool = False
        self.current_stage: str = "Idle"
        self.last_run_at: Optional[str] = None
        self.next_run_at: Optional[str] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start_background_loop(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_loop, name="SETSWatcherDaemon", daemon=True
        )
        self._thread.start()

    def stop_background_loop(self) -> None:
        self._stop_event.set()

    def _daemon_loop(self) -> None:
        while not self._stop_event.is_set():
            settings = get_settings()
            interval_mins = max(5, int(settings.get("scan_interval_minutes", 30)))
            now = datetime.now(timezone.utc)

            if settings.get("watcher_enabled", True):
                if self.next_run_at is None:
                    self.next_run_at = (
                        now + timedelta(minutes=interval_mins)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    try:
                        next_dt = datetime.strptime(
                            self.next_run_at, "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=timezone.utc)
                        if now >= next_dt and not self.is_scanning:
                            self.run_scan(trigger_type="scheduled")
                            self.next_run_at = (
                                datetime.now(timezone.utc)
                                + timedelta(minutes=interval_mins)
                            ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        self.next_run_at = (
                            now + timedelta(minutes=interval_mins)
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                self.next_run_at = None

            self._stop_event.wait(10.0)

    def get_status(self) -> Dict[str, Any]:
        settings = get_settings()
        return {
            "watcher_enabled": bool(settings.get("watcher_enabled", True)),
            "scan_interval_minutes": int(settings.get("scan_interval_minutes", 30)),
            "is_scanning": self.is_scanning,
            "current_stage": self.current_stage,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "last_result": self.last_result,
        }

    def run_scan(self, trigger_type: str = "manual") -> Dict[str, Any]:
        with self._lock:
            if self.is_scanning:
                return {
                    "ok": False,
                    "message": "A scan is already in progress.",
                    "status": self.get_status(),
                }
            self.is_scanning = True
            self.current_stage = "Initializing discovery queries..."

        scan_id = log_scan_start(trigger_type)
        settings = get_settings()
        min_score = int(settings.get("min_relevance_score", 55))
        sim_threshold = float(settings.get("dedup_similarity_threshold", 0.62))

        queries_run = 0
        raw_count = 0
        duplicates_skipped = 0
        saved_count = 0
        notified_count = 0

        try:
            self.current_stage = "Scanning LinkedIn, Web, Tenders, News & Reddit..."
            discovered_items, queries_run, errors = run_multi_source_discovery(
                settings, max_queries=8
            )
            raw_count = len(discovered_items)

            for idx, item in enumerate(discovered_items):
                url = item.get("url", "")
                title = item.get("title", "")
                if not title or not url:
                    continue

                # Pre-check against existing database leads for URL or Title similarity
                is_dup, _, _, _ = check_duplicate_or_similar_lead(
                    item, similarity_threshold=sim_threshold
                )
                if is_dup:
                    duplicates_skipped += 1
                    continue

                self.current_stage = (
                    f"AI analyzing item {idx + 1}/{raw_count}: {title[:45]}..."
                )
                analyzed = analyze_item(item, settings)

                if (
                    analyzed.get("is_genuine_enquiry", True)
                    and int(analyzed.get("relevance_score", 0)) >= min_score
                ):
                    lead_id, dup_reason = insert_lead(
                        analyzed,
                        check_duplicates=True,
                        similarity_threshold=sim_threshold,
                    )
                    if lead_id:
                        saved_count += 1
                        saved_lead = get_lead_by_id(lead_id) or analyzed
                        notify_res = notify_for_lead(saved_lead, settings, force=False)
                        notified_count += notify_res.get("sent_count", 0)
                    elif dup_reason:
                        duplicates_skipped += 1

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.last_run_at = now_iso
            interval_mins = max(5, int(settings.get("scan_interval_minutes", 30)))
            self.next_run_at = (
                datetime.now(timezone.utc) + timedelta(minutes=interval_mins)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            details_msg = (
                f"Scanned {queries_run} queries, found {raw_count} posts, "
                f"blocked {duplicates_skipped} duplicates/similar, "
                f"saved {saved_count} new leads, sent {notified_count} alerts."
            )
            if errors:
                details_msg += f" Warnings: {'; '.join(errors[:2])}"

            log_scan_complete(
                scan_id,
                "completed",
                queries_run,
                raw_count,
                saved_count,
                notified_count,
                details_msg,
                duplicates_skipped=duplicates_skipped,
            )

            result = {
                "ok": True,
                "scan_id": scan_id,
                "queries_run": queries_run,
                "raw_items_found": raw_count,
                "duplicates_skipped": duplicates_skipped,
                "new_leads_saved": saved_count,
                "notifications_sent": notified_count,
                "details": details_msg,
            }
            self.last_result = result
            return result

        except Exception as exc:
            err_str = f"Scan failed: {exc}"
            log_scan_complete(
                scan_id,
                "failed",
                queries_run,
                raw_count,
                saved_count,
                notified_count,
                err_str,
                duplicates_skipped=duplicates_skipped,
            )
            result = {"ok": False, "error": err_str}
            self.last_result = result
            return result

        finally:
            self.current_stage = "Idle"
            self.is_scanning = False

    def analyze_custom_post(
        self,
        title: str,
        snippet: str,
        url: str = "",
        source_platform: str = "LinkedIn",
        save_to_db: bool = True,
        send_notifications: bool = False,
    ) -> Dict[str, Any]:
        settings = get_settings()
        sim_threshold = float(settings.get("dedup_similarity_threshold", 0.62))
        item = {
            "title": title or snippet[:90] or "Manual Enquiry Analysis",
            "snippet": snippet,
            "url": url or f"https://www.sets4us.com/manual-lead/{int(time.time())}",
            "source_platform": source_platform,
            "force_ai": True,
        }
        analyzed = analyze_item(item, settings)
        lead_id = None
        duplicate_reason = None
        notify_res = {"sent_count": 0}

        if save_to_db:
            lead_id, duplicate_reason = insert_lead(
                analyzed,
                check_duplicates=True,
                similarity_threshold=sim_threshold,
            )
            if lead_id:
                analyzed["id"] = lead_id
                if send_notifications:
                    notify_res = notify_for_lead(analyzed, settings, force=True)

        return {
            "ok": True,
            "lead": analyzed,
            "saved_lead_id": lead_id,
            "is_duplicate": duplicate_reason is not None,
            "duplicate_reason": duplicate_reason,
            "notifications": notify_res,
        }


watcher_engine = WatcherEngine()
