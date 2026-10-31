"""
Pure-Python Professional Multi-Page PDF Document Generator for SETS AI Lead Watcher (www.sets4us.com).
Generates:
1. D:\\PYTHON\\MARKET\\SETS_How_To_Install_Guide.pdf
2. D:\\PYTHON\\MARKET\\SETS_How_To_Use_User_Manual.pdf
"""

import os
import textwrap
from datetime import datetime
from typing import List, Tuple


def _escape_pdf_text(text: str) -> str:
    # Replace non-latin1 characters with clean ASCII equivalents for standard Type1 Helvetica
    replacements = {
        "•": "-",
        "—": "-",
        "–": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "≥": ">=",
        "≤": "<=",
        "→": "->",
        "↗": "->",
        "✓": "[OK]",
        "✅": "[OK]",
        "⚡": "[*]",
        "🌱": "[*]",
        "🏢": "[*]",
        "📊": "[*]",
        "🌍": "[*]",
        "🏗️": "[*]",
        "📡": "[*]",
        "🗄️": "[*]",
        "👥": "[*]",
        "🧠": "[*]",
        "⚙️": "[*]",
        "📋": "[*]",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    clean = text.encode("latin-1", errors="ignore").decode("latin-1")
    return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class SimplePDFBuilder:
    """Builds a multi-page A4 PDF (595 x 842 pt) using standard Helvetica & Helvetica-Bold fonts."""

    PAGE_W = 595
    PAGE_H = 842
    MARGIN_X = 45

    def __init__(self, doc_title: str, doc_subtitle: str) -> None:
        self.doc_title = doc_title
        self.doc_subtitle = doc_subtitle
        self.pages: List[List[str]] = []
        self.current_cmds: List[str] = []
        self.y = 0
        self._start_new_page(is_first=True)

    def _start_new_page(self, is_first: bool = False) -> None:
        if self.current_cmds:
            self.pages.append(self.current_cmds)
        self.current_cmds = []

        # Top header banner (Emerald & Navy)
        if is_first:
            # Deep Navy/Emerald Banner at top of Page 1
            self.current_cmds.append("0.04 0.30 0.23 rg")
            self.current_cmds.append(f"0 {self.PAGE_H - 95} {self.PAGE_W} 95 re f")
            self.current_cmds.append("0.06 0.72 0.50 rg")
            self.current_cmds.append(f"0 {self.PAGE_H - 99} {self.PAGE_W} 4 re f")

            # Banner text
            self.current_cmds.append("1 1 1 rg")
            self._draw_text_line(self.MARGIN_X, self.PAGE_H - 36, "SETS AI LEAD WATCHER (64-BIT WINDOWS)", bold=True, size=16)
            self.current_cmds.append("0.65 0.95 0.82 rg")
            self._draw_text_line(self.MARGIN_X, self.PAGE_H - 56, self.doc_title, bold=True, size=13)
            self.current_cmds.append("0.85 0.92 0.95 rg")
            self._draw_text_line(self.MARGIN_X, self.PAGE_H - 76, self.doc_subtitle, bold=False, size=9.5)
            self.y = self.PAGE_H - 125
        else:
            # Running header on subsequent pages
            self.current_cmds.append("0.06 0.10 0.18 rg")
            self.current_cmds.append(f"0 {self.PAGE_H - 42} {self.PAGE_W} 42 re f")
            self.current_cmds.append("0.40 0.90 0.72 rg")
            self._draw_text_line(
                self.MARGIN_X,
                self.PAGE_H - 26,
                f"SETS AI Lead Watcher (www.sets4us.com)  |  {self.doc_title}",
                bold=True,
                size=9.5,
            )
            self.y = self.PAGE_H - 68

        # Reset text color to dark slate
        self.current_cmds.append("0.10 0.14 0.20 rg")

    def _ensure_space(self, needed_pt: float) -> None:
        if self.y - needed_pt < 55:
            self._start_new_page(is_first=False)

    def _draw_text_line(self, x: float, y: float, text: str, bold: bool = False, size: float = 10.5) -> None:
        font_ref = "/F2" if bold else "/F1"
        esc = _escape_pdf_text(text)
        self.current_cmds.append(f"BT {font_ref} {size} Tf {x:.1f} {y:.1f} Td ({esc}) Tj ET")

    def add_section_heading(self, title: str) -> None:
        self._ensure_space(38)
        self.y -= 8
        # Light emerald/slate background bar for section heading
        self.current_cmds.append("0.92 0.97 0.95 rg")
        self.current_cmds.append(f"{self.MARGIN_X - 4} {self.y - 6} {self.PAGE_W - 2 * self.MARGIN_X + 8} 22 re f")
        self.current_cmds.append("0.04 0.47 0.34 rg")
        self.current_cmds.append(f"{self.MARGIN_X - 4} {self.y - 6} 4 22 re f")
        self.current_cmds.append("0.05 0.25 0.18 rg")
        self._draw_text_line(self.MARGIN_X + 6, self.y + 1, title, bold=True, size=11.5)
        self.current_cmds.append("0.10 0.14 0.20 rg")
        self.y -= 20

    def add_subheading(self, text: str) -> None:
        self._ensure_space(24)
        self.y -= 4
        self.current_cmds.append("0.06 0.32 0.24 rg")
        self._draw_text_line(self.MARGIN_X, self.y, text, bold=True, size=10.5)
        self.current_cmds.append("0.10 0.14 0.20 rg")
        self.y -= 15

    def add_paragraph(self, text: str, indent: float = 0.0, bold: bool = False, size: float = 10.0) -> None:
        wrap_width = int((self.PAGE_W - 2 * self.MARGIN_X - indent) / (size * 0.50))
        lines = textwrap.wrap(text, width=max(45, wrap_width))
        for line in lines:
            self._ensure_space(15)
            self._draw_text_line(self.MARGIN_X + indent, self.y, line, bold=bold, size=size)
            self.y -= 13.5
        self.y -= 3

    def add_bullet(self, title_prefix: str, body: str) -> None:
        full_text = f"- {title_prefix}: {body}" if title_prefix else f"- {body}"
        lines = textwrap.wrap(full_text, width=88)
        for idx, line in enumerate(lines):
            self._ensure_space(15)
            x_pos = self.MARGIN_X + (8 if idx == 0 else 18)
            is_bold = idx == 0 and bool(title_prefix) and len(lines) == 1
            self._draw_text_line(x_pos, self.y, line, bold=is_bold, size=9.8)
            self.y -= 13.5
        self.y -= 1.5

    def add_code_box(self, lines: List[str]) -> None:
        box_h = len(lines) * 13 + 12
        self._ensure_space(box_h + 8)
        top_y = self.y + 8
        self.current_cmds.append("0.95 0.96 0.98 rg")
        self.current_cmds.append(
            f"{self.MARGIN_X + 6} {top_y - box_h} {self.PAGE_W - 2 * self.MARGIN_X - 12} {box_h} re f"
        )
        self.current_cmds.append("0.15 0.22 0.34 rg")
        for ln in lines:
            self._draw_text_line(self.MARGIN_X + 14, self.y - 2, ln, bold=False, size=9.2)
            self.y -= 13
        self.current_cmds.append("0.10 0.14 0.20 rg")
        self.y -= 10

    def save(self, output_path: str) -> None:
        if self.current_cmds:
            self.pages.append(self.current_cmds)
            self.current_cmds = []

        total_pages = len(self.pages)
        # Add footer with page numbers to every page
        for idx, cmds in enumerate(self.pages):
            cmds.append("0.45 0.50 0.58 rg")
            footer_str = _escape_pdf_text(
                f"SETS (www.sets4us.com) - AI Lead & Building Permit Watcher   |   Page {idx + 1} of {total_pages}"
            )
            cmds.append(f"BT /F1 8.5 Tf {self.MARGIN_X} 26 Td ({footer_str}) Tj ET")

        # Assemble valid PDF binary
        objects: List[bytes] = []

        def add_obj(content: bytes) -> int:
            objects.append(content)
            return len(objects)

        # Obj 1: Catalog (placeholder updated after Pages object)
        add_obj(b"")
        # Obj 2: Pages (placeholder updated after page objects)
        add_obj(b"")
        # Obj 3: Font F1 (Helvetica)
        f1_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        # Obj 4: Font F2 (Helvetica-Bold)
        f2_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        page_obj_ids: List[int] = []
        for cmds in self.pages:
            stream_bytes = "\n".join(cmds).encode("latin-1", errors="ignore")
            content_id = add_obj(
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
                + stream_bytes
                + b"\nendstream"
            )
            page_dict = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.PAGE_W} {self.PAGE_H}] "
                f"/Resources << /Font << /F1 {f1_id} 0 R /F2 {f2_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
            page_id = add_obj(page_dict)
            page_obj_ids.append(page_id)

        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_obj_ids)} >>".encode("ascii")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: List[int] = [0]
        for idx, obj_bytes in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(f"{idx} 0 obj\n".encode("ascii"))
            out.extend(obj_bytes)
            out.extend(b"\nendobj\n")

        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        out.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
                "ascii"
            )
        )

        with open(output_path, "wb") as f:
            f.write(out)


def build_installation_guide_pdf(output_path: str) -> None:
    pdf = SimplePDFBuilder(
        doc_title="DOCUMENT 1: HOW TO INSTALL THE SOFTWARE",
        doc_subtitle="Step-by-Step 64-Bit Windows Setup Wizard, PostgreSQL Setup & Android Phone Installation",
    )

    pdf.add_section_heading("1. Overview & System Requirements")
    pdf.add_paragraph(
        "SETS AI Lead & Building Permit Watcher is packaged into a self-contained 64-Bit Windows Setup Wizard "
        "(SETS_AI_Watcher_Setup_x64.exe). It checks prerequisites, verifies PostgreSQL connectivity, sets up all databases "
        "and multi-user profiles, and creates desktop shortcuts with the official SETS logo icon. "
        "Colleagues and team members do NOT need to install Python or manually configure code to run the software."
    )
    pdf.add_bullet("Supported Operating System", "Windows 10 or Windows 11 (64-Bit / x64 Architecture).")
    pdf.add_bullet("Installer File to Share with Colleagues", "SETS_AI_Watcher_Setup_x64.exe (located in installation package).")
    pdf.add_bullet("Standalone Executable File", "SETS_AI_Lead_Watcher_x64.exe (can also run directly without installation).")
    pdf.add_bullet("Database Prior Requirement", "PostgreSQL 14, 15, 16, or 18 (Local or Cloud like Neon.tech / Supabase). Checked in Step 1.")

    pdf.add_section_heading("2. Step-by-Step Installation Using SETS_AI_Watcher_Setup_x64.exe")
    pdf.add_paragraph(
        "Double-click SETS_AI_Watcher_Setup_x64.exe on any 64-Bit Windows PC to launch the interactive Setup Wizard:"
    )

    pdf.add_subheading("Step 1 of 4: Prior Requirement — PostgreSQL Database Verification")
    pdf.add_bullet("Automated PostgreSQL Detection", "The wizard immediately probes localhost port 5432 to check if PostgreSQL is already active and running.")
    pdf.add_bullet("Option A: Existing / Cloud PostgreSQL URI", "If you have a PostgreSQL database (local or free cloud like Neon.tech or Supabase), enter your connection URI and click 'Test Connection'.")
    pdf.add_bullet("Option B: One-Click Auto-Install via Winget", "Click 'Auto-Install PostgreSQL (winget)' to have Windows Package Manager download and install official 64-bit PostgreSQL silently.")
    pdf.add_bullet("Option C: Official PostgreSQL Download", "Click 'Download PostgreSQL' to open the official EnterpriseDB Windows installer if you prefer manual setup.")

    pdf.add_subheading("Step 2 of 4: Destination Directory & Desktop Icon Selection")
    pdf.add_bullet("64-Bit Architecture Verification", "The installer confirms 64-bit Windows compatibility and DPAPI encryption capability.")
    pdf.add_bullet("Installation Path", "Accept the default path (C:\\Users\\<Name>\\AppData\\Local\\Programs\\SETS_AI_Lead_Watcher) or select a custom folder.")
    pdf.add_bullet("Desktop Shortcut", "Keep 'Create Desktop Shortcut with SETS Logo Icon' checked to pin the application with the SETS Shield icon.")

    pdf.add_subheading("Step 3 of 4: Automated Component & Multi-User Profile Installation")
    pdf.add_paragraph(
        "Click 'Install Now (Step-by-Step)' to begin the automated setup process:"
    )
    pdf.add_code_box([
        "[Step 1/6] Verifying 64-Bit OS & creating isolated target directories...",
        "[Step 2/6] Installing SETS_AI_Lead_Watcher_x64.exe & SETS Logo Icon...",
        "[Step 3/6] Initializing PostgreSQL Tables & Multi-User Isolated Vaults...",
        "[Step 4/6] Setting up Open-Source WhatsApp Bridge & Web Search Frameworks...",
        "[Step 5/6] Creating Desktop Shortcut ('SETS AI Lead Watcher') with SETS Logo...",
        "[Step 6/6] Zero Preloaded Info Enforced: Clean slate profile ready!",
    ])

    pdf.add_subheading("Step 4 of 4: Finish & Launch Application")
    pdf.add_bullet(
        "Instant Launch",
        "Click 'Finish & Launch SETS AI Lead Watcher'. The native SETS Control Center and the full dashboard interface will open automatically.",
    )

    pdf.add_section_heading("3. Clean Slate & Multi-User Profile Isolation Guarantee")
    pdf.add_paragraph(
        "The software enforces strict multi-user privacy and persistence:"
    )
    pdf.add_bullet("Zero Default Information", "The app launches completely clean with NO preloaded demo leads, contacts, or hardcoded personal phone numbers.")
    pdf.add_bullet("Profile Persistence", "When a user logs in (e.g. 'Zakariya' or 'Engineer_1'), all their configured search areas, custom keywords, portal cookies, contacts, and tender enquiries persist and automatically pop up on their next launch.")
    pdf.add_bullet("Complete Isolation", "If a different colleague logs in with a different username, none of the previous user's data is displayed. Each user gets an independent, encrypted vault.")

    pdf.add_section_heading("4. Setting Up Free WhatsApp Alerts (Optional)")
    pdf.add_paragraph(
        "To enable free automated background WhatsApp messages from your PC:"
    )
    pdf.add_bullet("Step 1", "Double-click 'start_whatsapp_bridge.bat' in the installation folder (or click 'Start Open-Source WhatsApp Bridge' in the control window).")
    pdf.add_bullet("Step 2", "A browser tab will open at http://127.0.0.1:3001 displaying a QR Code.")
    pdf.add_bullet("Step 3", "On your phone, open WhatsApp -> Settings -> Linked Devices -> Link a Device, and scan the QR code on screen.")
    pdf.add_bullet("Step 4", "Once linked, the status badge turns green ('CONNECTED & READY') and the AI Watcher will automatically dispatch alerts to whatever phone numbers are configured in your Team Contacts tab!")

    pdf.add_section_heading("5. Installing the Android Phone Application (.APK)")
    pdf.add_bullet("Step 1 - Transfer APK", "Send SETS_AI_Lead_Watcher_Android.apk to your Android phone via WhatsApp, USB, or Google Drive.")
    pdf.add_bullet("Step 2 - Tap to Install", "Tap the APK on your phone. If prompted, allow 'Install from this source' and confirm.")
    pdf.add_bullet("Step 3 - Launch App", "Open 'SETS AI Watcher' from your app drawer. It features phone-optimized bottom navigation, thumb-friendly buttons, and runs either autonomously offline or connected to your PostgreSQL server.")

    pdf.save(output_path)


def build_user_manual_pdf(output_path: str) -> None:
    pdf = SimplePDFBuilder(
        doc_title="DOCUMENT 2: HOW TO USE THE SOFTWARE (USER MANUAL)",
        doc_subtitle="Complete Guide to Multi-User Profiles, Search Areas, API Plans, LinkedIn & Building Permits",
    )

    pdf.add_section_heading("1. Multi-User Profile Vault & Session Persistence")
    pdf.add_paragraph(
        "SETS AI Lead Watcher is built for multi-user enterprise teams with complete data isolation:"
    )
    pdf.add_bullet("User Profile Header", "Look at the top-right corner of the dashboard to see the active user badge (e.g. '👤 Alex' or '👤 Engineer_1'). Click it at any time to open the Profile Vault modal.")
    pdf.add_bullet("Creating / Switching Profiles", "Enter a new username to create a clean-slate profile, or select an existing colleague from the dropdown to switch instantly.")
    pdf.add_bullet("Data Persistence", "All configured municipal search areas, custom keywords, team contacts, and tender inquiries are saved to that specific user and automatically restored whenever they launch the application.")

    pdf.add_section_heading("2. Tab 1: Live Enquiries & LinkedIn Server Search")
    pdf.add_paragraph(
        "Your real-time intelligence feed for www.sets4us.com services (Energy Audit, BMS, CMS, Sustainability Audit, ESG Reporting) across UAE, KSA, and India."
    )
    pdf.add_bullet("Live On-Demand Search Bar", "Type any requirement keyword (e.g. 'BMS tender Dubai', 'ASHRAE Audit Riyadh', 'ESG consultant Mumbai') and click 'Fetch Live LinkedIn & Web Results'.")
    pdf.add_bullet("Direct WhatsApp Alerting", "Click '📲 Send to WhatsApp' to instantly open a pre-formatted lead brief addressed to your profile's configured team WhatsApp recipient.")
    pdf.add_bullet("Point of Contact Extraction", "Displays Contact Name, Role, Organization, Location, verified Email, and clickable Phone/WhatsApp call buttons.")
    pdf.add_bullet("Tailored Sales Pitch", "Click '📋 Copy Pitch' to get an AI-crafted proposal message referencing SETS capabilities ready to send to the client.")

    pdf.add_section_heading("3. Tab 2: New Buildings & User-Configurable Search Areas")
    pdf.add_paragraph(
        "Tracks newly approved building permits, MEP tenders, and industrial projects across UAE and Indian municipal corporations."
    )
    pdf.add_subheading("A. User-Configurable Municipal Search Areas")
    pdf.add_bullet("Configuring Your Own Areas", "Click '+ Add Custom Search Area' to monitor specific cities, states, or municipal corporations (e.g. 'Pune Municipal Corporation (PMC)', 'Bangalore BBMP', 'Sharjah SEWA', 'Riyadh Mun').")
    pdf.add_bullet("Keyword Targeting", "Assign target keywords (e.g. 'MEP, BMS, Energy Audit, Chiller, High-Rise') and portal URLs per area.")
    pdf.add_bullet("Active / Pause Toggles", "Toggle any search area on or off with a single click. Each user configures their own independent search areas.")

    pdf.add_subheading("B. Building Permit Details & Stakeholders")
    pdf.add_bullet("Stakeholders Identified", "Every permit card identifies: 1) Client / Developer, 2) Engineering / MEP Consultant, and 3) Main / MEP Contractor.")
    pdf.add_bullet("Direct Contact Information", "Point-of-contact name, email, phone number, and official municipal portal verification links.")

    pdf.add_section_heading("4. Tab 3: Search Previous Enquiries (Historical Database)")
    pdf.add_paragraph(
        "Search and audit your entire historical database of past inquiries with multi-criteria filtering:"
    )
    pdf.add_bullet("Filters", "Filter by Keyword, POC Name/Phone/Email, Service Category, Region, Date Range, and AI Relevance Score.")
    pdf.add_bullet("CSV / Excel Export", "Click '📥 Export Results to CSV' to download a complete spreadsheet of matching records.")

    pdf.add_section_heading("5. Tab 4: Team Numbers & Emails Configuration")
    pdf.add_paragraph(
        "Manage team members who receive automated alerts. Starts with zero preloaded entries for a clean slate:"
    )
    pdf.add_bullet("Anti-Duplication Protection", "The system automatically prevents duplicate entries by verifying Name, Phone, and Email against existing team records.")
    pdf.add_bullet("Region Filters", "Assign recipients to receive alerts for 'All Regions', 'UAE Only', 'KSA Only', or 'India Only'.")
    pdf.add_bullet("Test Dispatch", "Click 'Test WA' or 'Test Email' to verify message delivery to any individual team member.")

    pdf.add_section_heading("6. Tab 5: Portal Login & API Access Plan")
    pdf.add_paragraph(
        "Points out the specific logins, cookies, and APIs required to access restricted portals, with step-by-step instructions:"
    )
    pdf.add_bullet("1. Direct LinkedIn Session (li_at Cookie)", "Why required: LinkedIn restricts guest searches. Access plan: Log in to linkedin.com in your browser -> Press F12 -> Application -> Cookies -> Copy 'li_at' cookie value -> Paste in the form. Encrypted per user.")
    pdf.add_bullet("2. Google Gemini AI API", "Why required: Parses web notices and extracts contact info using AI. Access plan: Visit aistudio.google.com to generate a free API key (free tier includes 15 RPM).")
    pdf.add_bullet("3. Google Custom Search (CSE)", "Why required: Indexes municipal tender announcements and gazettes. Access plan: Create a free Google Cloud API key and Custom Search Engine ID (100 queries/day free).")
    pdf.add_bullet("4. Municipal Portals & UAE PASS", "Why required: Public registers (Dubai DM, Abu Dhabi MePS, K-SMART, TS-bPASS) work directly. For detailed architectural packages, enter your UAE PASS or municipal SSO ID.")

    pdf.add_section_heading("7. Tab 6: PostgreSQL & Notification Settings")
    pdf.add_bullet("PostgreSQL Connection", "Enter your local or cloud PostgreSQL URI, test connectivity, and sync databases.")
    pdf.add_bullet("WhatsApp Provider", "Select between SETS Free Local Bridge (Baileys), WAHA, CallMeBot, Meta Cloud API, or Twilio.")
    pdf.add_bullet("Anti-Duplication Threshold", "Adjust similarity cutoff (default 0.62) to prevent reposted inquiries.")

    pdf.add_section_heading("8. Tab 7: Security Shield & Mobile Sync")
    pdf.add_bullet("Security Safeguards", "Windows DPAPI encryption, Android FLAG_SECURE screenshot blocker, 4-digit PIN lock, brute force lockout, and isolated sandboxing.")
    pdf.add_bullet("Android APK Parity", "The Android APK provides 100% feature parity with the PC application, tailored for phone touch screens.")

    pdf.save(output_path)


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    install_pdf = os.path.join(base_dir, "SETS_How_To_Install_Guide.pdf")
    usage_pdf = os.path.join(base_dir, "SETS_How_To_Use_User_Manual.pdf")
    build_installation_guide_pdf(install_pdf)
    build_user_manual_pdf(usage_pdf)
    print(f"Generated PDF 1: {install_pdf}")
    print(f"Generated PDF 2: {usage_pdf}")

