"""
SETS AI Lead Watcher - 64-Bit Windows Step-by-Step Setup Wizard (SETS_AI_Watcher_Setup_x64.exe)
Step 1: PostgreSQL Database — install it (winget / manual) or connect to an existing server,
        verify the login and create the application database
Step 2: Installation Destination Folder & Shortcuts (SETS Logo Icon)
Step 3: Automated Step-by-Step Installation
Step 4: Completion & Launch
"""

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional, Tuple

from watcher.pg_admin import DEFAULT_APP_ROLE, provision_app_login


def get_bundled_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return os.path.dirname(os.path.abspath(__file__))


BUNDLED_DIR = get_bundled_dir()
ICON_PATH = os.path.join(BUNDLED_DIR, "assets", "sets_logo.ico")

PG_WINGET_ID = "PostgreSQL.PostgreSQL.17"
PG_DOWNLOAD_URL = "https://www.postgresql.org/download/windows/"
APP_DB_NAME = "sets_watcher"
# Characters that survive being passed through winget --override to the EDB installer
PG_PASSWORD_RE = re.compile(r"^[A-Za-z0-9@#$%^*_\-+=!.,:~]{6,64}$")
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

BG = "#0b1120"
CARD = "#111827"
FG = "#f8fafc"
MUTED = "#cbd5e1"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"
BLUE = "#38bdf8"


def is_64bit_windows() -> bool:
    machine = platform.machine().upper()
    return machine in ("AMD64", "X86_64", "ARM64") or "PROGRAMFILES(X86)" in os.environ


def check_port_open(host: str = "127.0.0.1", port: int = 5432, timeout: float = 1.5) -> bool:
    try:
        target = "127.0.0.1" if host.strip().lower() == "localhost" else host.strip()
        with socket.create_connection((target, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def find_installed_postgres_versions() -> list:
    base = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "PostgreSQL")
    try:
        return sorted(
            (d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "bin", "postgres.exe"))),
            key=lambda v: int(re.sub(r"\D", "", v) or 0),
        )
    except Exception:
        return []


def winget_available() -> bool:
    return shutil.which("winget") is not None


def friendly_pg_error(exc: Exception) -> str:
    raw = str(exc)
    if "28P01" in raw or "password authentication failed" in raw:
        return "Password authentication failed — check the user name and password."
    if "timed out" in raw.lower() or "10061" in raw or "refused" in raw.lower() or "create a connection" in raw.lower():
        return "Could not reach the PostgreSQL server — is it installed and running?"
    if "getaddrinfo" in raw or "11001" in raw:
        return "Host name not found — check the server address."
    m = re.search(r"'M': '([^']+)'", raw)
    return m.group(1) if m else raw[:180]


def verify_and_prepare_database(params: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Log in with the given credentials, create the application database if it is
    missing, and confirm we can connect to it. Returns (ok, message).
    """
    try:
        import pg8000.dbapi
    except ImportError:
        return False, "Internal error: PostgreSQL driver (pg8000) is missing from the installer."

    host = "127.0.0.1" if params["host"] in ("localhost", "") else params["host"]
    ssl_ctx = True if params.get("sslmode") in ("require", "verify-ca", "verify-full") else None
    dbname = params["dbname"]
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_\-]{0,62}$", dbname):
        return False, f"Invalid database name: {dbname!r}"

    def _connect(database: str):
        return pg8000.dbapi.connect(
            host=host,
            port=int(params["port"]),
            database=database,
            user=params["user"],
            password=params["password"],
            timeout=8,
            ssl_context=ssl_ctx,
        )

    created = False
    try:
        conn = _connect(dbname)
    except Exception as exc:
        raw = str(exc)
        if "3D000" not in raw and "does not exist" not in raw:
            return False, friendly_pg_error(exc)
        # Database missing: create it via the maintenance database
        try:
            admin = _connect("postgres")
            admin.autocommit = True
            admin.cursor().execute(f'CREATE DATABASE "{dbname}"')
            admin.close()
            created = True
            conn = _connect(dbname)
        except Exception as exc2:
            return False, f"Logged in, but could not create database '{dbname}': {friendly_pg_error(exc2)}"
    try:
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = str(cur.fetchone()[0]).split(",")[0]
    finally:
        conn.close()
    action = f"created database '{dbname}'" if created else f"database '{dbname}' is ready"
    return True, f"Connected to {version} — {action}."


def create_windows_shortcut(target_exe: str, shortcut_path: str, icon_path: str, working_dir: str, description: str) -> bool:
    """Create a Windows .lnk shortcut with the SETS Logo icon using PowerShell WScript.Shell."""

    def q(v: str) -> str:
        return v.replace("'", "''")

    ps_script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{q(shortcut_path)}'); "
        f"$s.TargetPath = '{q(target_exe)}'; "
        f"$s.WorkingDirectory = '{q(working_dir)}'; "
        f"$s.IconLocation = '{q(icon_path)},0'; "
        f"$s.Description = '{q(description)}'; "
        f"$s.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


class SetsInstallerWizard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SETS AI Lead Watcher (64-Bit) - Setup Wizard")
        self.root.geometry("800x680")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        if os.path.isfile(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        default_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "Programs",
            "SETS_AI_Lead_Watcher",
        )
        self.install_dir_var = tk.StringVar(value=default_dir)

        # PostgreSQL connection fields
        self.pg_host_var = tk.StringVar(value="localhost")
        self.pg_port_var = tk.StringVar(value="5432")
        self.pg_user_var = tk.StringVar(value="postgres")
        self.pg_pass_var = tk.StringVar(value="")
        self.pg_db_var = tk.StringVar(value=APP_DB_NAME)
        self.pg_uri_var = tk.StringVar(value="")
        self.new_pw_var = tk.StringVar(value="")
        self.new_pw2_var = tk.StringVar(value="")
        self.pg_status_msg = tk.StringVar(value="")
        self.pg_verified = False
        self.pg_busy = False
        self.verified_params: Dict[str, Any] = {}
        self.create_app_login_var = tk.BooleanVar(value=True)
        self.app_login: Optional[Tuple[str, str]] = None  # (login, generated password)

        self.setup_wa_bridge_var = tk.BooleanVar(value=True)
        self.create_desktop_icon_var = tk.BooleanVar(value=True)
        self.create_startmenu_var = tk.BooleanVar(value=True)
        self.launch_after_install_var = tk.BooleanVar(value=True)

        self.current_step = 1
        self._build_layout()
        self._show_step_1()

    # ------------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        self.banner = tk.Frame(self.root, bg="#064e3b", padx=24, pady=14)
        self.banner.pack(fill="x")
        tk.Label(
            self.banner,
            text="SETS AI Lead Watcher • 64-Bit Windows Setup Wizard",
            font=("Segoe UI", 14, "bold"),
            fg=FG,
            bg="#064e3b",
        ).pack(anchor="w")
        self.banner_sub = tk.Label(self.banner, text="", font=("Segoe UI", 9), fg="#a7f3d0", bg="#064e3b")
        self.banner_sub.pack(anchor="w", pady=(3, 0))

        self.footer = tk.Frame(self.root, bg="#0f172a", padx=24, pady=12)
        self.footer.pack(fill="x", side="bottom")
        self.btn_back = tk.Button(
            self.footer, text="← Back", command=self._on_back, bg="#1e293b", fg=MUTED,
            font=("Segoe UI", 10), padx=16, pady=6, relief="flat", state="disabled",
        )
        self.btn_back.pack(side="left")
        self.btn_next = tk.Button(
            self.footer, text="Next →", command=self._on_next, bg="#10b981", fg="#052e16",
            font=("Segoe UI", 10, "bold"), padx=18, pady=6, relief="flat", cursor="hand2",
        )
        self.btn_next.pack(side="right")

        self.content = tk.Frame(self.root, bg=BG, padx=24, pady=12)
        self.content.pack(fill="both", expand=True)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _label(self, parent, text, size=9, bold=False, fg=MUTED, bg=CARD, **pack):
        lbl = tk.Label(
            parent, text=text, font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=fg, bg=bg, justify="left", anchor="w", wraplength=720,
        )
        lbl.pack(anchor="w", **pack)
        return lbl

    def _entry(self, parent, var, width=18, show=None):
        return tk.Entry(
            parent, textvariable=var, width=width, show=show, font=("Segoe UI", 9),
            bg=BG, fg=FG, insertbackground=FG, relief="flat",
        )

    def _button(self, parent, text, cmd, primary=False):
        return tk.Button(
            parent, text=text, command=cmd, bg="#065f46" if primary else "#1e293b",
            fg="#ecfdf5" if primary else FG, font=("Segoe UI", 9, "bold"),
            padx=12, pady=4, relief="flat", cursor="hand2",
        )

    def _set_status(self, text: str, color: str) -> None:
        def _ui() -> None:
            self.pg_status_msg.set(text)
            if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
                self.lbl_status.config(fg=color)

        self.root.after(0, _ui)

    # ---------------------------------------------------------- step 1: postgres
    def _show_step_1(self) -> None:
        self.current_step = 1
        self.banner_sub.config(text="Step 1 of 4: PostgreSQL database — where all your leads and projects are stored permanently")
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="normal", text="Next: Installation Folder →", command=self._on_next)
        self._clear_content()

        self._label(
            self.content,
            "SETS AI Lead Watcher stores every enquiry, building project and discovered website in a PostgreSQL "
            "database, so your history is kept safely and can be searched at any time. Choose A if PostgreSQL is "
            "not installed on this computer yet, or B if you already have a PostgreSQL server (local or cloud).",
            bg=BG, pady=(0, 8),
        )

        stat_card = tk.Frame(self.content, bg=CARD, padx=12, pady=8)
        stat_card.pack(fill="x", pady=(0, 8))
        self.lbl_status = tk.Label(
            stat_card, textvariable=self.pg_status_msg, font=("Segoe UI", 9, "bold"),
            fg=AMBER, bg=CARD, justify="left", anchor="w", wraplength=720,
        )
        self.lbl_status.pack(anchor="w")
        self._detect_existing_postgres()

        tk.Checkbutton(
            self.content,
            text=f"Create a dedicated database login '{DEFAULT_APP_ROLE}' for the app (recommended) — the app will "
                 "not use the 'postgres' administrator account",
            variable=self.create_app_login_var, bg=BG, fg=FG, selectcolor=CARD, font=("Segoe UI", 9),
            activebackground=BG, activeforeground=FG, wraplength=740, justify="left",
        ).pack(anchor="w", pady=(0, 4))

        # ---- Option A: install
        box_a = tk.LabelFrame(
            self.content, text=" A. Install PostgreSQL on this computer ", font=("Segoe UI", 9, "bold"),
            fg=BLUE, bg=CARD, padx=12, pady=8,
        )
        box_a.pack(fill="x", pady=4)
        self._label(
            box_a,
            "Choose a password for the PostgreSQL administrator account ('postgres'). Write it down — you need it "
            "to reconnect later. Allowed: letters, digits and @ # $ % ^ * _ - + = ! . , : ~ (6–64 characters).",
        )
        pw_row = tk.Frame(box_a, bg=CARD)
        pw_row.pack(fill="x", pady=(4, 4))
        tk.Label(pw_row, text="Password:", font=("Segoe UI", 9), fg=MUTED, bg=CARD).pack(side="left")
        self._entry(pw_row, self.new_pw_var, width=20, show="•").pack(side="left", padx=(4, 12), ipady=3)
        tk.Label(pw_row, text="Confirm:", font=("Segoe UI", 9), fg=MUTED, bg=CARD).pack(side="left")
        self._entry(pw_row, self.new_pw2_var, width=20, show="•").pack(side="left", padx=(4, 0), ipady=3)

        btn_row = tk.Frame(box_a, bg=CARD)
        btn_row.pack(fill="x", pady=(4, 2))
        has_winget = winget_available()
        self.btn_auto_install = self._button(
            btn_row, "⬇️ Install PostgreSQL 17 automatically", self._auto_install_postgres, primary=True
        )
        self.btn_auto_install.pack(side="left", padx=(0, 10))
        if not has_winget:
            self.btn_auto_install.config(state="disabled")
        self._button(btn_row, "🌐 Manual download page", lambda: webbrowser.open(PG_DOWNLOAD_URL)).pack(side="left")
        self._label(
            box_a,
            ("Automatic install uses Windows Package Manager (winget). Windows will ask for administrator "
             "permission; installation takes about 3–8 minutes." if has_winget else
             "winget is not available on this PC, so use the manual download."),
            fg="#94a3b8", pady=(4, 0),
        )
        self._label(
            box_a,
            "Manual install: run the official installer, keep port 5432, set the password, untick Stack Builder "
            "at the end, then enter the same password under B and click 'Test & create database'.",
            fg="#94a3b8",
        )

        # ---- Option B: connect
        box_b = tk.LabelFrame(
            self.content, text=" B. Connect to an existing PostgreSQL server (local or cloud) ",
            font=("Segoe UI", 9, "bold"), fg=BLUE, bg=CARD, padx=12, pady=8,
        )
        box_b.pack(fill="x", pady=(8, 4))
        grid = tk.Frame(box_b, bg=CARD)
        grid.pack(fill="x")
        fields = [
            ("Host", self.pg_host_var, 16, None),
            ("Port", self.pg_port_var, 6, None),
            ("User", self.pg_user_var, 12, None),
            ("Password", self.pg_pass_var, 14, "•"),
            ("Database", self.pg_db_var, 13, None),
        ]
        for col, (lbl, var, w, show) in enumerate(fields):
            tk.Label(grid, text=lbl, font=("Segoe UI", 8), fg="#94a3b8", bg=CARD).grid(row=0, column=col, sticky="w", padx=(0, 6))
            self._entry(grid, var, width=w, show=show).grid(row=1, column=col, sticky="w", padx=(0, 6), ipady=3)

        uri_row = tk.Frame(box_b, bg=CARD)
        uri_row.pack(fill="x", pady=(8, 4))
        tk.Label(
            uri_row, text="Or cloud URI (Neon / Supabase / RDS):", font=("Segoe UI", 8), fg="#94a3b8", bg=CARD
        ).pack(side="left")
        self._entry(uri_row, self.pg_uri_var, width=48).pack(side="left", padx=(6, 0), ipady=3, fill="x", expand=True)

        self.btn_test = self._button(box_b, "🔌 Test & create database", self._test_connection_clicked, primary=True)
        self.btn_test.pack(anchor="w", pady=(6, 0))

    def _detect_existing_postgres(self) -> None:
        versions = find_installed_postgres_versions()
        port_open = check_port_open("127.0.0.1", 5432)
        if self.pg_verified:
            return
        if port_open:
            ver = f" (PostgreSQL {versions[-1]} found)" if versions else ""
            self._set_status(
                f"✅ A PostgreSQL server is running on this computer{ver}. Enter its password under B and click "
                "'Test & create database'.", GREEN,
            )
        elif versions:
            self._set_status(
                f"⚠️ PostgreSQL {versions[-1]} is installed but not running. Start the 'postgresql' service in "
                "Windows Services, then use B to connect.", AMBER,
            )
        else:
            self._set_status(
                "⚠️ PostgreSQL was not found on this computer. Install it with option A (recommended), or connect "
                "to a cloud database with option B.", AMBER,
            )

    def _collect_params(self) -> Dict[str, Any]:
        params = {
            "host": self.pg_host_var.get().strip() or "localhost",
            "port": int(self.pg_port_var.get().strip() or 5432),
            "user": self.pg_user_var.get().strip() or "postgres",
            "password": self.pg_pass_var.get(),
            "dbname": self.pg_db_var.get().strip() or APP_DB_NAME,
            "sslmode": "prefer",
        }
        uri = self.pg_uri_var.get().strip()
        if uri.startswith(("postgres://", "postgresql://")):
            parsed = urllib.parse.urlparse(uri)
            params["host"] = parsed.hostname or params["host"]
            params["port"] = parsed.port or 5432
            params["user"] = urllib.parse.unquote(parsed.username or params["user"])
            params["password"] = urllib.parse.unquote(parsed.password or params["password"])
            params["dbname"] = parsed.path.lstrip("/") or params["dbname"]
            qs = urllib.parse.parse_qs(parsed.query)
            params["sslmode"] = (qs.get("sslmode") or ["require"])[0]
        return params

    def _set_busy(self, busy: bool) -> None:
        def _ui() -> None:
            self.pg_busy = busy
            state = "disabled" if busy else "normal"
            for btn in (getattr(self, "btn_test", None), getattr(self, "btn_auto_install", None), self.btn_next):
                if btn is not None and btn.winfo_exists():
                    if btn is getattr(self, "btn_auto_install", None) and not winget_available():
                        continue
                    btn.config(state=state)

        self.root.after(0, _ui)

    def _test_connection_clicked(self) -> None:
        if self.pg_busy:
            return
        try:
            params = self._collect_params()
        except ValueError:
            self._set_status("⚠️ Port must be a number.", RED)
            return
        self._set_busy(True)
        self._set_status(f"⏳ Connecting to {params['host']}:{params['port']} as '{params['user']}'...", BLUE)

        create_login = self.create_app_login_var.get()

        def _worker() -> None:
            ok, msg = verify_and_prepare_database(params)
            final, extra, colour, app_login = (params, "", GREEN, None)
            if ok:
                self._set_status(f"⏳ {msg} Setting up the app login...", BLUE)
                final, extra, colour, app_login = self._finalize_connection(params, create_login)

            def _apply() -> None:
                self.pg_verified = ok
                if ok:
                    self.verified_params = final
                    self.app_login = app_login
                self._set_status(f"✅ {msg}{extra}" if ok else f"❌ {msg}", colour if ok else RED)
                self._set_busy(False)

            self.root.after(0, _apply)

        threading.Thread(target=_worker, daemon=True).start()

    def _finalize_connection(self, admin_params: Dict[str, Any], create_login: bool) -> Tuple[Dict[str, Any], str, str, Optional[Tuple[str, str]]]:
        """
        After the administrator login is verified, optionally create the dedicated
        app login. Returns (params_to_save, status_suffix, colour, app_login).
        """
        if not create_login or admin_params["user"].lower() == DEFAULT_APP_ROLE:
            return admin_params, "", GREEN, None
        ok, msg, app_pw = provision_app_login(admin_params, admin_params["user"], admin_params["password"])
        if ok:
            final = dict(admin_params, user=DEFAULT_APP_ROLE, password=app_pw)
            return final, f" {msg} The app will sign in as '{DEFAULT_APP_ROLE}'.", GREEN, (DEFAULT_APP_ROLE, app_pw)
        return admin_params, (
            f" Could not create the '{DEFAULT_APP_ROLE}' login ({msg}); the app will use '{admin_params['user']}'."
        ), AMBER, None

    def _auto_install_postgres(self) -> None:
        if self.pg_busy:
            return
        pw, pw2 = self.new_pw_var.get(), self.new_pw2_var.get()
        if not PG_PASSWORD_RE.match(pw):
            messagebox.showwarning(
                "Password", "Please choose a 6–64 character password using letters, digits and @ # $ % ^ * _ - + = ! . , : ~"
            )
            return
        if pw != pw2:
            messagebox.showwarning("Password", "The two passwords do not match.")
            return
        if check_port_open("127.0.0.1", 5432):
            if not messagebox.askyesno(
                "PostgreSQL already running",
                "A PostgreSQL server is already running on port 5432. Installing another one is usually not needed — "
                "use option B with its password instead.\n\nInstall anyway?",
            ):
                return

        create_login = self.create_app_login_var.get()
        self._set_busy(True)
        self._set_status(
            "⏳ Installing PostgreSQL 17 via winget... approve the Windows administrator prompt if it appears. "
            "This can take several minutes — please keep this window open.", BLUE,
        )

        def _worker() -> None:
            override = (
                f"--mode unattended --unattendedmodeui minimal --superpassword {pw} "
                f"--serverport 5432 --disable-components stackbuilder"
            )
            cmd = [
                "winget", "install", "--id", PG_WINGET_ID, "-e", "--source", "winget",
                "--accept-source-agreements", "--accept-package-agreements", "--override", override,
            ]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=1800, creationflags=CREATE_NO_WINDOW,
                )
                out = (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired:
                self._set_status("❌ The installation timed out. Please use the manual download.", RED)
                self._set_busy(False)
                return
            except Exception as exc:
                self._set_status(f"❌ Could not start winget: {exc}. Please use the manual download.", RED)
                self._set_busy(False)
                return

            already = "already installed" in out.lower()
            if proc.returncode != 0 and not already:
                tail = " ".join(out.strip().split())[-220:]
                self._set_status(
                    f"❌ winget could not install PostgreSQL (exit code {proc.returncode}). {tail} "
                    "Please use the manual download.", RED,
                )
                self._set_busy(False)
                return

            self._set_status("⏳ PostgreSQL installed. Waiting for the database service to start...", BLUE)
            for _ in range(90):
                if check_port_open("127.0.0.1", 5432, timeout=1.0):
                    break
                time.sleep(2)
            else:
                self._set_status(
                    "⚠️ PostgreSQL was installed but the service is not answering on port 5432 yet. Restart the "
                    "computer or start the 'postgresql' service, then use B to connect.", AMBER,
                )
                self._set_busy(False)
                return

            params = {
                "host": "localhost", "port": 5432, "user": "postgres", "password": pw,
                "dbname": self.pg_db_var.get().strip() or APP_DB_NAME, "sslmode": "prefer",
            }
            ok, msg = verify_and_prepare_database(params)
            if ok:
                final, extra, colour, app_login = self._finalize_connection(params, create_login)

                def _apply() -> None:
                    self.pg_verified = True
                    self.verified_params = final
                    self.app_login = app_login
                    self.pg_pass_var.set(pw)
                    self.pg_host_var.set("localhost")
                    self.pg_port_var.set("5432")
                    self.pg_user_var.set("postgres")

                self.root.after(0, _apply)
                self._set_status(f"✅ PostgreSQL installed. {msg}{extra}", colour)
            elif already:
                self._set_status(
                    f"⚠️ PostgreSQL was already installed, so its existing password was kept. Enter that password "
                    f"under B. ({msg})", AMBER,
                )
            else:
                self._set_status(f"⚠️ PostgreSQL installed, but the login test failed: {msg}", AMBER)
            self._set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------- step 2: folder
    def _show_step_2(self) -> None:
        self.current_step = 2
        self.banner_sub.config(text="Step 2 of 4: Installation Destination & Shortcuts with SETS Logo Icon")
        self.btn_back.config(state="normal")
        self.btn_next.config(state="normal", text="Install Now →", command=self._on_next)
        self._clear_content()

        os_ok = is_64bit_windows()
        arch_str = f"{platform.system()} {platform.release()} ({platform.machine()})"

        tk.Label(
            self.content, text="Select Installation Location & Shortcuts", font=("Segoe UI", 13, "bold"), fg=FG, bg=BG,
        ).pack(anchor="w", pady=(0, 8))

        chk_box = tk.Frame(self.content, bg=CARD, padx=16, pady=10)
        chk_box.pack(fill="x", pady=4)
        self._label(
            chk_box,
            f"{'✅' if os_ok else '⚠️'} Operating system: {arch_str if os_ok else 'Non-64-bit OS detected'}",
            bold=True, fg=GREEN if os_ok else RED,
        )
        db_line = (
            f"✅ Database: PostgreSQL at {self.verified_params['host']}:{self.verified_params['port']}/"
            f"{self.verified_params['dbname']} (verified)"
            if self.pg_verified
            else "⚠️ Database: PostgreSQL not connected — the app will use its built-in local store until you "
                 "connect PostgreSQL in Settings."
        )
        self._label(chk_box, db_line, fg=GREEN if self.pg_verified else AMBER, pady=(3, 0))
        self._label(chk_box, "✅ Saved passwords are encrypted with Windows DPAPI for your user account", fg=BLUE, pady=(3, 0))

        tk.Label(
            self.content, text="Destination Installation Folder:", font=("Segoe UI", 9, "bold"), fg=MUTED, bg=BG,
        ).pack(anchor="w", pady=(14, 4))

        dir_row = tk.Frame(self.content, bg=BG)
        dir_row.pack(fill="x")
        tk.Entry(
            dir_row, textvariable=self.install_dir_var, font=("Segoe UI", 9), bg=CARD, fg=FG,
            insertbackground=FG, relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        def browse_dir() -> None:
            chosen = filedialog.askdirectory(initialdir=self.install_dir_var.get())
            if chosen:
                self.install_dir_var.set(os.path.normpath(chosen))

        tk.Button(
            dir_row, text="Browse...", command=browse_dir, bg="#1e293b", fg=FG, font=("Segoe UI", 9),
            padx=12, pady=4, relief="flat",
        ).pack(side="right")

        opt_frame = tk.Frame(self.content, bg=CARD, padx=14, pady=10)
        opt_frame.pack(fill="x", pady=12)
        for text, var in (
            ("Create Desktop Shortcut with the SETS Logo icon", self.create_desktop_icon_var),
            ("Create Windows Start Menu shortcut", self.create_startmenu_var),
            ("Install the open-source WhatsApp Bridge files (optional, needs Node.js)", self.setup_wa_bridge_var),
        ):
            tk.Checkbutton(
                opt_frame, text=text, variable=var, bg=CARD, fg=FG, selectcolor=BG, font=("Segoe UI", 9),
                activebackground=CARD, activeforeground=FG,
            ).pack(anchor="w", pady=2)

    # ------------------------------------------------------------ step 3: install
    def _show_step_3_installing(self) -> None:
        self.current_step = 3
        self.banner_sub.config(text="Step 3 of 4: Installing SETS AI Lead Watcher...")
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled", text="Installing...")
        self._clear_content()

        tk.Label(
            self.content, text="Installing SETS AI Lead Watcher & Configuring Components...",
            font=("Segoe UI", 11, "bold"), fg=FG, bg=BG,
        ).pack(anchor="w", pady=(0, 8))

        self.progress = ttk.Progressbar(self.content, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 10))

        self.log_text = tk.Text(
            self.content, height=16, bg="#050811", fg=GREEN, font=("Consolas", 9), relief="flat", padx=10, pady=8,
        )
        self.log_text.pack(fill="both", expand=True)

        threading.Thread(target=self._run_installation_steps, daemon=True).start()

    def _append_log(self, msg: str, progress_val: int) -> None:
        def _ui() -> None:
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.progress["value"] = progress_val

        self.root.after(0, _ui)

    def _write_postgres_config(self, data_dir: str) -> str:
        """Write data/postgres_config.json in the format the app reads (password DPAPI-encrypted)."""
        if not self.pg_verified:
            return "skipped (not verified — connect later in Settings)"
        p = self.verified_params
        try:
            from watcher.security import encrypt_secret

            enc_pw = encrypt_secret(p["password"]) if p["password"] else ""
        except Exception:
            enc_pw = ""
        cfg = {
            # No password inside the URI: the app reads it from the encrypted field
            "postgres_url": f"postgresql://{urllib.parse.quote(p['user'], safe='')}@{p['host']}:{p['port']}/{p['dbname']}"
            + (f"?sslmode={p['sslmode']}" if p.get("sslmode") not in (None, "", "prefer") else ""),
            "postgres_host": p["host"],
            "postgres_port": int(p["port"]),
            "postgres_db": p["dbname"],
            "postgres_user": p["user"],
            "postgres_password": enc_pw,
            "postgres_sslmode": p.get("sslmode") or "prefer",
        }
        with open(os.path.join(data_dir, "postgres_config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return f"saved ({p['user']}@{p['host']}:{p['port']}/{p['dbname']})"

    def _run_installation_steps(self) -> None:
        install_dir = self.install_dir_var.get().strip()
        try:
            self._append_log("[Step 1/5] Creating installation folders...", 15)
            os.makedirs(install_dir, exist_ok=True)
            os.makedirs(os.path.join(install_dir, "assets"), exist_ok=True)
            data_dir = os.path.join(install_dir, "data")
            os.makedirs(data_dir, exist_ok=True)

            self._append_log("[Step 2/5] Installing SETS_AI_Lead_Watcher_x64.exe & SETS logo...", 35)
            bundled_exe = os.path.join(BUNDLED_DIR, "SETS_AI_Lead_Watcher_x64.exe")
            target_exe = os.path.join(install_dir, "SETS_AI_Lead_Watcher_x64.exe")
            if os.path.isfile(bundled_exe):
                shutil.copy2(bundled_exe, target_exe)
            else:
                dist_exe = os.path.join(BUNDLED_DIR, "dist", "SETS_AI_Lead_Watcher_x64.exe")
                if os.path.isfile(dist_exe):
                    shutil.copy2(dist_exe, target_exe)
                else:
                    self._append_log("    ! Application executable not found inside the installer.", 35)

            target_ico = os.path.join(install_dir, "assets", "sets_logo.ico")
            if os.path.isfile(ICON_PATH):
                shutil.copy2(ICON_PATH, target_ico)
            for helper_file in ("start_whatsapp_bridge.bat", "setup_postgres.bat", "README.md"):
                src_f = os.path.join(BUNDLED_DIR, helper_file)
                if os.path.isfile(src_f):
                    shutil.copy2(src_f, os.path.join(install_dir, helper_file))

            self._append_log("[Step 3/5] Saving PostgreSQL connection...", 60)
            self._append_log(f"    PostgreSQL: {self._write_postgres_config(data_dir)}", 62)

            if self.setup_wa_bridge_var.get():
                self._append_log("[Step 4/5] Copying open-source WhatsApp Bridge files...", 80)
                src_wa = os.path.join(BUNDLED_DIR, "whatsapp_bridge")
                dst_wa = os.path.join(install_dir, "whatsapp_bridge")
                if os.path.isdir(src_wa):
                    os.makedirs(dst_wa, exist_ok=True)
                    for fn in ("package.json", "server.js"):
                        s_file = os.path.join(src_wa, fn)
                        if os.path.isfile(s_file):
                            shutil.copy2(s_file, os.path.join(dst_wa, fn))
            else:
                self._append_log("[Step 4/5] WhatsApp Bridge skipped.", 80)

            self._append_log("[Step 5/5] Creating shortcuts...", 95)
            exe_to_link = target_exe if os.path.isfile(target_exe) else sys.executable
            icon = target_ico if os.path.isfile(target_ico) else exe_to_link
            if self.create_desktop_icon_var.get():
                desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                create_windows_shortcut(
                    exe_to_link, os.path.join(desktop_dir, "SETS AI Lead Watcher.lnk"), icon, install_dir,
                    "SETS AI Lead Watcher (www.sets4us.com)",
                )
            if self.create_startmenu_var.get():
                start_menu_dir = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")), "Microsoft", "Windows", "Start Menu", "Programs",
                )
                if os.path.isdir(start_menu_dir):
                    create_windows_shortcut(
                        exe_to_link, os.path.join(start_menu_dir, "SETS AI Lead Watcher.lnk"), icon, install_dir,
                        "SETS AI Lead Watcher (www.sets4us.com)",
                    )

            self._append_log("[Complete] Setup finished.", 100)
            self.root.after(700, lambda: self._show_step_4_finish(target_exe, install_dir))

        except Exception as exc:
            self._append_log(f"[ERROR] Installation encountered an error: {exc}", 100)
            self.root.after(0, lambda: self.btn_back.config(state="normal"))

    # ------------------------------------------------------------- step 4: finish
    def _show_step_4_finish(self, target_exe: str, install_dir: str) -> None:
        self.current_step = 4
        self.banner_sub.config(text="Step 4 of 4: Setup Completed Successfully")
        self.btn_back.config(state="disabled")
        self.btn_next.config(
            state="normal", text="Finish & Launch 🚀", command=lambda: self._finish_and_launch(target_exe, install_dir),
        )
        self._clear_content()

        tk.Label(
            self.content, text="🎉 SETS AI Lead Watcher is ready!", font=("Segoe UI", 14, "bold"), fg=GREEN, bg=BG,
        ).pack(anchor="w", pady=(0, 10))

        summary = tk.Frame(self.content, bg=CARD, padx=16, pady=14)
        summary.pack(fill="x", pady=8)
        self._label(summary, f"• Installed: {target_exe}", fg=FG, pady=2)
        if self.create_desktop_icon_var.get():
            self._label(summary, "• Desktop shortcut: 'SETS AI Lead Watcher'", fg="#a7f3d0", pady=2)
        if self.pg_verified:
            p = self.verified_params
            self._label(summary, f"• Database: PostgreSQL {p['host']}:{p['port']}/{p['dbname']} — all results are saved permanently", fg=BLUE, pady=2)
            if self.app_login:
                login, app_pw = self.app_login
                row = tk.Frame(summary, bg=CARD)
                row.pack(anchor="w", pady=2, fill="x")
                tk.Label(
                    row, text=f"• App database login: {login}   password: {app_pw}", font=("Consolas", 9),
                    fg="#a7f3d0", bg=CARD,
                ).pack(side="left")

                def _copy() -> None:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(app_pw)

                self._button(row, "Copy", _copy).pack(side="left", padx=8)
                self._label(
                    summary,
                    "  The app already has this password (stored encrypted). Keep a copy only if you want to open the "
                    "database in pgAdmin or psql; you can reset it any time from the app's Settings.",
                    fg="#94a3b8",
                )
        else:
            self._label(
                summary,
                "• Database: not connected yet. Open the app → '⚙️ Settings' → PostgreSQL, enter your connection and "
                "click 'Test & Connect'. Until then results are kept in the built-in local store.",
                fg=AMBER, pady=2,
            )
        self._label(
            summary,
            "• Market Watch: click 'Scan Now' on the dashboard, or wait for the automatic scan. Use '🩺 Check Live "
            "Sources' to see which websites are reachable from your network.",
            fg=MUTED, pady=2,
        )

        tk.Checkbutton(
            self.content, text="Launch SETS AI Lead Watcher now", variable=self.launch_after_install_var,
            bg=BG, fg=FG, selectcolor=CARD, font=("Segoe UI", 10, "bold"), activebackground=BG, activeforeground=FG,
        ).pack(anchor="w", pady=(14, 4))

    def _finish_and_launch(self, target_exe: str, install_dir: str) -> None:
        if self.launch_after_install_var.get():
            if os.path.isfile(target_exe):
                subprocess.Popen([target_exe], cwd=install_dir)
            else:
                app_py = os.path.join(BUNDLED_DIR, "app.py")
                if os.path.isfile(app_py):
                    subprocess.Popen([sys.executable, app_py], cwd=BUNDLED_DIR)
        self.root.destroy()

    # -------------------------------------------------------------- navigation
    def _on_back(self) -> None:
        if self.current_step == 2:
            self._show_step_1()

    def _on_next(self) -> None:
        if self.current_step == 1:
            if self.pg_busy:
                return
            if not self.pg_verified and not messagebox.askyesno(
                "Continue without PostgreSQL?",
                "PostgreSQL is not connected yet.\n\nYou can continue — the app will keep results in its built-in "
                "local store, and you can connect PostgreSQL later from Settings. For permanent storage it is "
                "recommended to set PostgreSQL up now.\n\nContinue without PostgreSQL?",
            ):
                return
            self._show_step_2()
        elif self.current_step == 2:
            self._show_step_3_installing()


if __name__ == "__main__":
    root = tk.Tk()
    wizard = SetsInstallerWizard(root)
    root.mainloop()
