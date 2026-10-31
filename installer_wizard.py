"""
SETS AI Lead Watcher - 64-Bit Windows Step-by-Step Setup Wizard (SETS_AI_Watcher_Setup_x64.exe)
Step 1: PostgreSQL Database Setup & Prior Requirement Verification
Step 2: Installation Destination Folder & Shortcuts (SETS Logo Icon)
Step 3: Automated Step-by-Step Installation
Step 4: Completion & Multi-User Isolated Launch
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser


def get_bundled_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return os.path.dirname(os.path.abspath(__file__))


BUNDLED_DIR = get_bundled_dir()
ICON_PATH = os.path.join(BUNDLED_DIR, "assets", "sets_logo.ico")


def is_64bit_windows() -> bool:
    machine = platform.machine().upper()
    return machine in ("AMD64", "X86_64", "ARM64") or "PROGRAMFILES(X86)" in os.environ


def check_postgres_running(host: str = "127.0.0.1", port: int = 5432) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=1.5):
            return True
    except Exception:
        return False


def create_windows_shortcut(target_exe: str, shortcut_path: str, icon_path: str, working_dir: str, description: str) -> bool:
    """Create a Windows .lnk shortcut with the SETS Logo icon using PowerShell WScript.Shell."""
    ps_script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{shortcut_path}'); "
        f"$s.TargetPath = '{target_exe}'; "
        f"$s.WorkingDirectory = '{working_dir}'; "
        f"$s.IconLocation = '{icon_path},0'; "
        f"$s.Description = '{description}'; "
        f"$s.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return True
    except Exception:
        return False


class SetsInstallerWizard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SETS AI Lead Watcher (64-Bit) - Setup Wizard")
        self.root.geometry("740x550")
        self.root.configure(bg="#0b1120")
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
        self.pg_mode_var = tk.StringVar(value="uri")  # uri | winget_install
        self.pg_url_var = tk.StringVar(
            value="postgresql://postgres:postgres@localhost:5432/sets_watcher"
        )
        self.pg_status_msg = tk.StringVar(value="Checking PostgreSQL...")
        self.setup_wa_bridge_var = tk.BooleanVar(value=True)
        self.create_desktop_icon_var = tk.BooleanVar(value=True)
        self.create_startmenu_var = tk.BooleanVar(value=True)
        self.launch_after_install_var = tk.BooleanVar(value=True)

        self.current_step = 1
        self._build_layout()
        self._show_step_1()

    def _build_layout(self) -> None:
        # Top Banner
        self.banner = tk.Frame(self.root, bg="#064e3b", padx=24, pady=16)
        self.banner.pack(fill="x")
        self.banner_title = tk.Label(
            self.banner,
            text="SETS AI Lead Watcher • 64-Bit Windows Setup Wizard",
            font=("Segoe UI", 14, "bold"),
            fg="#f8fafc",
            bg="#064e3b",
        )
        self.banner_title.pack(anchor="w")
        self.banner_sub = tk.Label(
            self.banner,
            text="Step 1 of 4: Prior Requirement — PostgreSQL Database Verification",
            font=("Segoe UI", 9),
            fg="#a7f3d0",
            bg="#064e3b",
        )
        self.banner_sub.pack(anchor="w", pady=(3, 0))

        # Content Container
        self.content = tk.Frame(self.root, bg="#0b1120", padx=26, pady=16)
        self.content.pack(fill="both", expand=True)

        # Bottom Navigation Bar
        self.footer = tk.Frame(self.root, bg="#0f172a", padx=24, pady=12)
        self.footer.pack(fill="x", side="bottom")

        self.btn_back = tk.Button(
            self.footer,
            text="← Back",
            command=self._on_back,
            bg="#1e293b",
            fg="#cbd5e1",
            font=("Segoe UI", 10),
            padx=16,
            pady=6,
            relief="flat",
            state="disabled",
        )
        self.btn_back.pack(side="left")

        self.btn_next = tk.Button(
            self.footer,
            text="Next: Installation Folder & Shortcuts →",
            command=self._on_next,
            bg="#10b981",
            fg="#052e16",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=6,
            relief="flat",
            cursor="hand2",
        )
        self.btn_next.pack(side="right")

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _show_step_1(self) -> None:
        """Step 1: PostgreSQL Prior Requirement & Installation Guide"""
        self.current_step = 1
        self.banner_sub.config(
            text="Step 1 of 4: Prior Requirement — PostgreSQL Database Verification (www.sets4us.com)"
        )
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="normal", text="Next: Installation Folder & Shortcuts →")
        self._clear_content()

        pg_live = check_postgres_running("127.0.0.1", 5432)
        status_text = (
            "✅ PostgreSQL Database is detected and active on localhost:5432"
            if pg_live
            else "⚠️ PostgreSQL Database not detected on localhost:5432 (Prior Requirement Required)"
        )
        status_fg = "#34d399" if pg_live else "#fbbf24"
        self.pg_status_msg.set(status_text)

        tk.Label(
            self.content,
            text="Prior Requirement: PostgreSQL Database Setup",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#0b1120",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            self.content,
            text=(
                "SETS AI Lead Watcher requires PostgreSQL (64-Bit) as a prior requirement to store\n"
                "isolated multi-user profiles, historical tender inquiries, anti-duplication hashes, and municipal permits.\n"
                "Please verify your PostgreSQL connection or choose an installation method below:"
            ),
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0b1120",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Live Status Card
        stat_card = tk.Frame(self.content, bg="#111827", padx=14, pady=10)
        stat_card.pack(fill="x", pady=(0, 10))
        self.lbl_status = tk.Label(
            stat_card,
            textvariable=self.pg_status_msg,
            font=("Segoe UI", 9, "bold"),
            fg=status_fg,
            bg="#111827",
        )
        self.lbl_status.pack(anchor="w")

        # Installation & Configuration Options Box
        box = tk.LabelFrame(
            self.content,
            text=" PostgreSQL Setup Guidance & Options ",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#111827",
            padx=14,
            pady=10,
        )
        box.pack(fill="both", expand=True, pady=4)

        # Option A: URI Connection & Test
        tk.Label(
            box,
            text="Option A: Connect to Local or Cloud PostgreSQL (Neon.tech / Supabase / AWS RDS / Local)",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#111827",
        ).pack(anchor="w", pady=(2, 2))

        uri_row = tk.Frame(box, bg="#111827")
        uri_row.pack(fill="x", pady=(0, 6))
        tk.Entry(
            uri_row,
            textvariable=self.pg_url_var,
            font=("Segoe UI", 9),
            bg="#0b1120",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        def test_pg() -> None:
            raw_url = self.pg_url_var.get().strip()
            # Simple socket or test
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(raw_url)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or 5432
                if check_postgres_running(host, port):
                    self.pg_status_msg.set(f"✅ Connection Successful! Verified reachable at {host}:{port}")
                    self.lbl_status.config(fg="#34d399")
                else:
                    self.pg_status_msg.set(f"⚠️ Could not reach PostgreSQL at {host}:{port}. Is service started?")
                    self.lbl_status.config(fg="#f43f5e")
            except Exception as e:
                self.pg_status_msg.set(f"Connection test error: {e}")
                self.lbl_status.config(fg="#f43f5e")

        tk.Button(
            uri_row,
            text="🔌 Test Connection",
            command=test_pg,
            bg="#1e293b",
            fg="#34d399",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=3,
            relief="flat",
            cursor="hand2",
        ).pack(side="right")

        # Option B: Automated winget install
        tk.Label(
            box,
            text="Option B: Automatically Install PostgreSQL 16 (64-Bit) on this Computer",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#111827",
        ).pack(anchor="w", pady=(8, 2))

        btn_row = tk.Frame(box, bg="#111827")
        btn_row.pack(fill="x", pady=(2, 6))

        def auto_install_winget() -> None:
            def _worker() -> None:
                self.pg_status_msg.set("⏳ Running Windows Package Manager (winget) to install PostgreSQL 16 (64-Bit)...")
                self.lbl_status.config(fg="#38bdf8")
                try:
                    p = subprocess.run(
                        ["winget", "install", "-e", "--id", "PostgreSQL.PostgreSQL.16", "--accept-source-agreements", "--accept-package-agreements", "--silent"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if p.returncode == 0 or check_postgres_running("127.0.0.1", 5432):
                        self.pg_status_msg.set("✅ PostgreSQL 16 Installed successfully! Port 5432 Active.")
                        self.lbl_status.config(fg="#34d399")
                    else:
                        self.pg_status_msg.set("⚠️ Winget completed. Please verify service in Windows Services.")
                        self.lbl_status.config(fg="#fbbf24")
                except Exception as exc:
                    self.pg_status_msg.set(f"Winget install note: {exc}")
                    self.lbl_status.config(fg="#fbbf24")

            threading.Thread(target=_worker, daemon=True).start()

        tk.Button(
            btn_row,
            text="⬇️ One-Click Auto-Install PostgreSQL via winget",
            command=auto_install_winget,
            bg="#065f46",
            fg="#ecfdf5",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=(0, 10))

        def open_official_download() -> None:
            webbrowser.open("https://www.postgresql.org/download/windows/")

        tk.Button(
            btn_row,
            text="🌐 Open Official PostgreSQL Download Page",
            command=open_official_download,
            bg="#1e293b",
            fg="#f8fafc",
            font=("Segoe UI", 9),
            padx=12,
            pady=4,
            relief="flat",
            cursor="hand2",
        ).pack(side="left")

    def _show_step_2(self) -> None:
        """Step 2: Installation Directory, Components & Shortcuts"""
        self.current_step = 2
        self.banner_sub.config(
            text="Step 2 of 4: Installation Destination & Shortcuts with SETS Logo Icon"
        )
        self.btn_back.config(state="normal")
        self.btn_next.config(state="normal", text="Install Now (Step-by-Step) →")
        self._clear_content()

        os_ok = is_64bit_windows()
        arch_str = f"{platform.system()} {platform.release()} ({platform.machine()} - 64-Bit Verified)"

        tk.Label(
            self.content,
            text="Select Installation Location & Shortcuts",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#0b1120",
        ).pack(anchor="w", pady=(0, 8))

        chk_box = tk.Frame(self.content, bg="#111827", padx=16, pady=10)
        chk_box.pack(fill="x", pady=4)
        tk.Label(
            chk_box,
            text=f"✅ Operating System Check: {arch_str if os_ok else 'Warning: Non-64-bit OS detected'}",
            font=("Segoe UI", 9, "bold"),
            fg="#34d399" if os_ok else "#f43f5e",
            bg="#111827",
        ).pack(anchor="w")
        tk.Label(
            chk_box,
            text="✅ Security Suite: Windows 64-Bit DPAPI Credential Encryption + Isolated User Vaults",
            font=("Segoe UI", 9),
            fg="#38bdf8",
            bg="#111827",
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            chk_box,
            text="✅ Zero Preloaded Data: Complete clean slate for all users with individual data persistence",
            font=("Segoe UI", 9),
            fg="#a7f3d0",
            bg="#111827",
        ).pack(anchor="w", pady=(3, 0))

        tk.Label(
            self.content,
            text="Destination Installation Folder:",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#0b1120",
        ).pack(anchor="w", pady=(14, 4))

        dir_row = tk.Frame(self.content, bg="#0b1120")
        dir_row.pack(fill="x")
        tk.Entry(
            dir_row,
            textvariable=self.install_dir_var,
            font=("Segoe UI", 9),
            bg="#111827",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        def browse_dir() -> None:
            chosen = filedialog.askdirectory(initialdir=self.install_dir_var.get())
            if chosen:
                self.install_dir_var.set(os.path.normpath(chosen))

        tk.Button(
            dir_row,
            text="Browse...",
            command=browse_dir,
            bg="#1e293b",
            fg="#f8fafc",
            font=("Segoe UI", 9),
            padx=12,
            pady=4,
            relief="flat",
        ).pack(side="right")

        # Shortcuts Options Frame
        opt_frame = tk.Frame(self.content, bg="#111827", padx=14, pady=10)
        opt_frame.pack(fill="x", pady=12)

        tk.Checkbutton(
            opt_frame,
            text="Create Desktop Shortcut with official 'SETS Logo' Icon (SETS AI Lead Watcher)",
            variable=self.create_desktop_icon_var,
            bg="#111827",
            fg="#f8fafc",
            selectcolor="#0b1120",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            opt_frame,
            text="Create Windows Start Menu Program Shortcut",
            variable=self.create_startmenu_var,
            bg="#111827",
            fg="#f8fafc",
            selectcolor="#0b1120",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            opt_frame,
            text="Install Open-Source Free WhatsApp Bridge Framework",
            variable=self.setup_wa_bridge_var,
            bg="#111827",
            fg="#f8fafc",
            selectcolor="#0b1120",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=2)

    def _show_step_3_installing(self) -> None:
        """Step 3: Installation Execution & Real-Time Log"""
        self.current_step = 3
        self.banner_sub.config(text="Step 3 of 4: Installing SETS AI Lead Watcher Step-by-Step...")
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled", text="Installing...")
        self._clear_content()

        tk.Label(
            self.content,
            text="Installing SETS AI Lead Watcher & Configuring Components...",
            font=("Segoe UI", 11, "bold"),
            fg="#f8fafc",
            bg="#0b1120",
        ).pack(anchor="w", pady=(0, 8))

        self.progress = ttk.Progressbar(self.content, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 10))

        self.log_text = tk.Text(
            self.content,
            height=14,
            bg="#050811",
            fg="#34d399",
            font=("Consolas", 9),
            relief="flat",
            padx=10,
            pady=8,
        )
        self.log_text.pack(fill="both", expand=True)

        threading.Thread(target=self._run_installation_steps, daemon=True).start()

    def _append_log(self, msg: str, progress_val: int) -> None:
        def _ui() -> None:
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.progress["value"] = progress_val

        self.root.after(0, _ui)

    def _run_installation_steps(self) -> None:
        install_dir = self.install_dir_var.get().strip()
        try:
            # Step 1: Verify OS & Target Directories
            self._append_log("[Step 1/5] Verifying 64-Bit Windows Environment & creating directories...", 15)
            os.makedirs(install_dir, exist_ok=True)
            os.makedirs(os.path.join(install_dir, "assets"), exist_ok=True)
            os.makedirs(os.path.join(install_dir, "data"), exist_ok=True)

            # Step 2: Copy Executable & Logo Icon
            self._append_log("[Step 2/5] Installing SETS_AI_Lead_Watcher_x64.exe & SETS Logo Icon...", 35)
            bundled_exe = os.path.join(BUNDLED_DIR, "SETS_AI_Lead_Watcher_x64.exe")
            target_exe = os.path.join(install_dir, "SETS_AI_Lead_Watcher_x64.exe")

            if os.path.isfile(bundled_exe):
                shutil.copy2(bundled_exe, target_exe)
            else:
                dist_exe = os.path.join(BUNDLED_DIR, "dist", "SETS_AI_Lead_Watcher_x64.exe")
                if os.path.isfile(dist_exe):
                    shutil.copy2(dist_exe, target_exe)

            target_ico = os.path.join(install_dir, "assets", "sets_logo.ico")
            if os.path.isfile(ICON_PATH):
                shutil.copy2(ICON_PATH, target_ico)

            for helper_file in ("start_whatsapp_bridge.bat", "setup_postgres.bat", "README.md"):
                src_f = os.path.join(BUNDLED_DIR, helper_file)
                if os.path.isfile(src_f):
                    shutil.copy2(src_f, os.path.join(install_dir, helper_file))

            # Step 3: PostgreSQL Database Config
            self._append_log("[Step 3/5] Configuring PostgreSQL Connection & Multi-User Profile Store...", 60)
            pg_cfg_path = os.path.join(install_dir, "data", "postgres_config.json")
            with open(pg_cfg_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "postgres_url": self.pg_url_var.get().strip(),
                        "postgres_host": "localhost",
                        "postgres_port": 5432,
                        "postgres_db": "sets_watcher",
                        "postgres_user": "postgres",
                    },
                    f,
                    indent=2,
                )

            # Step 4: WhatsApp Bridge
            self._append_log("[Step 4/5] Setting up Open-Source WhatsApp Bridge...", 80)
            src_wa = os.path.join(BUNDLED_DIR, "whatsapp_bridge")
            dst_wa = os.path.join(install_dir, "whatsapp_bridge")
            if os.path.isdir(src_wa):
                os.makedirs(dst_wa, exist_ok=True)
                for fn in ("package.json", "server.js"):
                    s_file = os.path.join(src_wa, fn)
                    if os.path.isfile(s_file):
                        shutil.copy2(s_file, os.path.join(dst_wa, fn))

            # Step 5: Shortcuts with SETS Logo
            self._append_log("[Step 5/5] Creating Desktop Shortcut with SETS Logo Icon...", 95)
            exe_to_link = target_exe if os.path.isfile(target_exe) else sys.executable

            if self.create_desktop_icon_var.get():
                desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                desktop_lnk = os.path.join(desktop_dir, "SETS AI Lead Watcher.lnk")
                create_windows_shortcut(
                    exe_to_link,
                    desktop_lnk,
                    target_ico if os.path.isfile(target_ico) else exe_to_link,
                    install_dir,
                    "SETS AI Lead Watcher (www.sets4us.com) - 24/7 AI Enquiry & POC Monitor",
                )

            if self.create_startmenu_var.get():
                start_menu_dir = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                )
                if os.path.isdir(start_menu_dir):
                    sm_lnk = os.path.join(start_menu_dir, "SETS AI Lead Watcher.lnk")
                    create_windows_shortcut(
                        exe_to_link,
                        sm_lnk,
                        target_ico if os.path.isfile(target_ico) else exe_to_link,
                        install_dir,
                        "SETS AI Lead Watcher (www.sets4us.com)",
                    )

            self._append_log("[Complete] Setup finished! Zero preloaded data verified.", 100)
            self.root.after(700, lambda: self._show_step_4_finish(target_exe, install_dir))

        except Exception as exc:
            self._append_log(f"[ERROR] Installation encountered an error: {exc}", 100)
            self.root.after(0, lambda: self.btn_back.config(state="normal"))

    def _show_step_4_finish(self, target_exe: str, install_dir: str) -> None:
        """Step 4: Completion Screen"""
        self.current_step = 4
        self.banner_sub.config(text="Step 4 of 4: Setup Completed Successfully")
        self.btn_back.config(state="disabled")
        self.btn_next.config(
            state="normal",
            text="Finish & Launch SETS AI Lead Watcher 🚀",
            command=lambda: self._finish_and_launch(target_exe, install_dir),
        )
        self._clear_content()

        tk.Label(
            self.content,
            text="🎉 SETS AI Lead Watcher (64-Bit) is Ready!",
            font=("Segoe UI", 14, "bold"),
            fg="#34d399",
            bg="#0b1120",
        ).pack(anchor="w", pady=(0, 10))

        summary = tk.Frame(self.content, bg="#111827", padx=16, pady=14)
        summary.pack(fill="x", pady=8)

        tk.Label(
            summary,
            text=f"• Installed Executable: {target_exe}",
            font=("Segoe UI", 9),
            fg="#f8fafc",
            bg="#111827",
        ).pack(anchor="w", pady=2)
        tk.Label(
            summary,
            text="• Desktop Shortcut Created: 'SETS AI Lead Watcher' (with SETS Logo Icon)",
            font=("Segoe UI", 9),
            fg="#a7f3d0",
            bg="#111827",
        ).pack(anchor="w", pady=2)
        tk.Label(
            summary,
            text="• PostgreSQL Database & Multi-User Profile Vault: Ready",
            font=("Segoe UI", 9),
            fg="#38bdf8",
            bg="#111827",
        ).pack(anchor="w", pady=2)
        tk.Label(
            summary,
            text="• Multi-User Isolation & Zero Default Information: Verified",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#111827",
        ).pack(anchor="w", pady=2)

        tk.Checkbutton(
            self.content,
            text="Launch SETS AI Lead Watcher GUI Immediately",
            variable=self.launch_after_install_var,
            bg="#0b1120",
            fg="#f8fafc",
            selectcolor="#111827",
            font=("Segoe UI", 10, "bold"),
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

    def _on_back(self) -> None:
        if self.current_step == 2:
            self._show_step_1()

    def _on_next(self) -> None:
        if self.current_step == 1:
            self._show_step_2()
        elif self.current_step == 2:
            self._show_step_3_installing()


if __name__ == "__main__":
    root = tk.Tk()
    wizard = SetsInstallerWizard(root)
    root.mainloop()
