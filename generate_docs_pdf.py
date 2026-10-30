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
        doc_title="DOCUMENT 1: HOW TO INSTALL THE SOFTWARE (64-BIT WINDOWS)",
        doc_subtitle="Step-by-Step Installation, PostgreSQL Database & Open-Source WhatsApp Bridge Setup Guide",
    )

    pdf.add_section_heading("1. Overview & System Requirements")
    pdf.add_paragraph(
        "The SETS AI Lead Watcher (www.sets4us.com) is packaged as a self-contained 64-Bit Windows application. "
        "Colleagues and team members do NOT need to install Python or manually configure code to run the software."
    )
    pdf.add_bullet("Supported Operating System", "Windows 10 or Windows 11 (64-Bit / x64 Architecture).")
    pdf.add_bullet("Installer File to Share with Colleagues", "SETS_AI_Watcher_Setup_x64.exe (located in D:\\PYTHON\\MARKET).")
    pdf.add_bullet("Standalone Executable File", "SETS_AI_Lead_Watcher_x64.exe (can also be run directly without installation).")
    pdf.add_bullet("Optional for Automated Local WhatsApp Bridge", "Node.js (64-Bit) if using the free self-hosted Baileys WhatsApp bridge on port 3001.")

    pdf.add_section_heading("2. Step-by-Step Installation Using SETS_AI_Watcher_Setup_x64.exe")
    pdf.add_paragraph(
        "Double-click SETS_AI_Watcher_Setup_x64.exe on any 64-Bit Windows PC to launch the interactive 4-step Setup Wizard:"
    )

    pdf.add_subheading("Step 1 of 4: Welcome & 64-Bit Windows OS Verification")
    pdf.add_bullet("OS & Security Check", "The wizard automatically verifies that your PC is running 64-Bit Windows and confirms that Windows DPAPI Credential Encryption is active.")
    pdf.add_bullet("Destination Folder", "Accept the default installation path (C:\\Users\\<YourName>\\AppData\\Local\\Programs\\SETS_AI_Lead_Watcher) or click 'Browse...' to select a custom folder, then click 'Next: Frameworks & Database ->'.")

    pdf.add_subheading("Step 2 of 4: Frameworks, PostgreSQL Database & Desktop Icon Selection")
    pdf.add_bullet(
        "Option A - Use Cloud or Existing PostgreSQL URI (Recommended for Team Sharing)",
        "Select 'Use Free Cloud PostgreSQL (Neon.tech / Supabase) or Existing Local PostgreSQL URI' and enter your connection string. If you leave the default URL and do not have a PostgreSQL server running yet, the app automatically uses its built-in local SQL cache so it works immediately!",
    )
    pdf.add_bullet(
        "Option B - Auto-Install Local PostgreSQL 16 (64-Bit)",
        "Select 'Download & Install PostgreSQL 16 (64-Bit) Automatically via Windows Package Manager (winget)' to have the installer silently install PostgreSQL 16 on the PC.",
    )
    pdf.add_bullet(
        "Shortcuts & WhatsApp Framework",
        "Keep 'Create Desktop Shortcut with SETS Logo Icon' and 'Install Open-Source Free WhatsApp Bridge Framework (+918138858961)' checked, then click 'Install Now (Step-by-Step) ->'.",
    )

    pdf.add_subheading("Step 3 of 4: Automated Step-by-Step Component Installation")
    pdf.add_paragraph(
        "Watch the progress bar and live console log as the wizard executes all 6 installation stages:"
    )
    pdf.add_code_box([
        "[Step 1/6] Verifying 64-Bit Windows OS & creating target directories...",
        "[Step 2/6] Installing SETS_AI_Lead_Watcher_x64.exe & SETS Logo Icon...",
        "[Step 3/6] Configuring PostgreSQL Database & DPAPI Security Store...",
        "[Step 4/6] Setting up Open-Source WhatsApp Bridge (+918138858961)...",
        "[Step 5/6] Creating Desktop Icon ('SETS AI Lead Watcher') with SETS Logo...",
        "[Step 6/6] Installation & Security Verification Complete!",
    ])

    pdf.add_subheading("Step 4 of 4: Finish & Launch Application GUI")
    pdf.add_bullet(
        "Auto-Launch",
        "Keep 'Launch SETS AI Lead Watcher GUI Immediately' checked and click 'Finish & Launch SETS AI Lead Watcher'. Both the SETS Native Desktop Control Window and the Full Interactive Dashboard GUI will open automatically.",
    )

    pdf.add_section_heading("3. Setting Up a Free Shared PostgreSQL Database (Optional)")
    pdf.add_paragraph(
        "If you want all colleagues to share a single live central database of enquiries and building permits for free:"
    )
    pdf.add_bullet("Step 1", "Create a free account at https://neon.tech or https://supabase.com (both offer free forever PostgreSQL tiers).")
    pdf.add_bullet("Step 2", "Copy your PostgreSQL Connection URI (e.g. postgresql://user:pass@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require).")
    pdf.add_bullet("Step 3", "Open the SETS AI Lead Watcher app -> go to the 'PostgreSQL, LinkedIn & WhatsApp Settings' tab -> paste the URI into 'PostgreSQL Connection URI' -> click 'Test & Connect PostgreSQL' -> click 'Save All Settings'.")

    pdf.add_section_heading("4. Setting Up the Free Open-Source WhatsApp Bridge (+918138858961)")
    pdf.add_paragraph(
        "Your Indian WhatsApp number (+918138858961) is pre-configured by default. To enable 100% free automated background WhatsApp messages from your PC:"
    )
    pdf.add_bullet("Step 1", "Double-click 'start_whatsapp_bridge.bat' in the installation folder (or click the green 'Start Open-Source WhatsApp Bridge (+918138858961)' button in the SETS Desktop Control Center window).")
    pdf.add_bullet("Step 2", "A browser tab will open at http://127.0.0.1:3001 displaying a QR Code.")
    pdf.add_bullet("Step 3", "On your phone, open WhatsApp -> Settings -> Linked Devices -> Link a Device, and scan the QR code on screen.")
    pdf.add_bullet("Step 4", "Once linked, the status badge turns green ('CONNECTED & READY') and the AI Watcher will automatically send all high-priority lead alerts to +918138858961 and all active numbers in your Team Contacts tab!")

    pdf.add_section_heading("5. Security Features Built Into the Installation")
    pdf.add_bullet("Windows 64-Bit DPAPI & Android AES-256 Encryption", "All API keys, database passwords, LinkedIn cookies, and SMTP passwords are encrypted at rest using Windows CryptProtectData (DPAPI) on PC and AES-256 Vault on Android.")
    pdf.add_bullet("Localhost Isolation, FLAG_SECURE & CSP", "Binds strictly to 127.0.0.1 on PC, blocks spyware screen recording via Android FLAG_SECURE on phones, and enforces Content-Security-Policy (CSP), PIN Lockout, and rate limiting.")

    pdf.add_section_heading("6. Installing the Android Phone Application (.APK)")
    pdf.add_paragraph(
        "You can also install the application on any Android smartphone or tablet using SETS_AI_Lead_Watcher_Android.apk:"
    )
    pdf.add_bullet("Step 1 - Transfer the APK", "Send SETS_AI_Lead_Watcher_Android.apk (located in D:\\PYTHON\\MARKET) to your Android phone via WhatsApp, Email, Google Drive, or USB cable.")
    pdf.add_bullet("Step 2 - Tap to Install", "Tap SETS_AI_Lead_Watcher_Android.apk on your phone. If prompted by Android, allow 'Install from this source' and tap 'Install'.")
    pdf.add_bullet("Step 3 - Launch from Home Screen", "Tap the 'SETS AI Watcher' icon (with the SETS Shield Logo) on your Android phone. It runs 100% autonomously on your phone and can also sync with your PC/PostgreSQL server.")

    pdf.save(output_path)


def build_user_manual_pdf(output_path: str) -> None:
    pdf = SimplePDFBuilder(
        doc_title="DOCUMENT 2: HOW TO USE THE SOFTWARE (USER MANUAL)",
        doc_subtitle="Complete Guide to All 7 Application Tabs, Live LinkedIn Search & Municipal Building Permits",
    )

    pdf.add_section_heading("1. Launching the Application & Desktop Control Window")
    pdf.add_paragraph(
        "Double-click the 'SETS AI Lead Watcher' icon (with the SETS Logo) on your Windows Desktop, or run SETS_AI_Lead_Watcher_x64.exe. "
        "Two windows open automatically:"
    )
    pdf.add_bullet(
        "1. SETS Native 64-Bit Desktop Control Center",
        "Shows live Watcher status, PostgreSQL connection health, total unique enquiries, duplicates blocked, and quick buttons to 'Open Full Dashboard GUI', 'Scan Internet Now', and 'Start Open-Source WhatsApp Bridge (+918138858961)'.",
    )
    pdf.add_bullet(
        "2. Full Interactive SETS AI Lead Watcher Dashboard Window",
        "Contains 7 navigation tabs across the top bar for managing leads, searching LinkedIn live, tracking municipal building permits, searching historical records, and configuring team contacts.",
    )

    pdf.add_section_heading("2. Tab 1: Live Enquiries & LinkedIn Search")
    pdf.add_paragraph(
        "This is your main real-time intelligence command center for www.sets4us.com activities (Energy Audit, Sustainability Audit, BMS, CMS, ESG Reporting) across UAE, KSA, and India."
    )
    pdf.add_subheading("A. Top KPI Summary Cards")
    pdf.add_bullet("Total Unique Enquiries", "Total deduplicated leads stored in your database.")
    pdf.add_bullet("High-Intent RFPs & Leads", "Enquiries scoring >= 75% AI relevance (RFPs, tenders, direct consultant searches).")
    pdf.add_bullet("Leads with Point of Contact", "Enquiries where the AI extracted a Contact Name, Email, or Phone/WhatsApp number.")
    pdf.add_bullet("Duplicates / Similar Blocked", "Count of reposted or similar enquiries automatically blocked by the Semantic Anti-Duplication Engine.")

    pdf.add_subheading("B. Live On-Demand LinkedIn Server & Internet Requirement Search Box")
    pdf.add_paragraph(
        "Located directly below the KPI cards (highlighted in emerald). Use this whenever you want to search LinkedIn and the Internet live for a specific requirement:"
    )
    pdf.add_bullet("How to Use", "1) Type any keyword (e.g. 'BMS tender Dubai', 'ASHRAE Audit Riyadh', 'ESG consultant Mumbai', 'Energy Audit Kochi'). 2) Choose the target Region (UAE, KSA, or India) and Service Category. 3) Click 'Fetch Live LinkedIn & Web Results'.")
    pdf.add_bullet("What Happens", "The engine queries LinkedIn's Guest Search API, LinkedIn Posts/Pulse indexers, Google News RSS, Bing RSS, DuckDuckGo, and Reddit in real time, runs AI qualification & anti-duplication, saves new leads, and refreshes the feed.")

    pdf.add_subheading("C. Working with Lead Cards")
    pdf.add_bullet("Filter Pills & Dropdowns", "Click any service pill (Energy Audit, Sustainability Audit, BMS, CMS, ESG Reporting) or filter by Region (UAE, KSA, India), Platform (LinkedIn, Web / Tenders, Reddit), or Status.")
    pdf.add_bullet("Extracted Point of Contact (POC)", "Displays Contact Name, Role, Company, Location, clickable Email, and clickable Phone/WhatsApp link.")
    pdf.add_bullet("Suggested SETS Outreach Pitch", "Click 'Copy Pitch' to copy a ready-to-send sales message tailored to the enquiry.")
    pdf.add_bullet("One-Click Alert Buttons", "Click 'WhatsApp Alert to Team' (sends via automated bridge), 'Send to +918138858961 (WA Web)' (opens WhatsApp directly with pre-filled lead summary), or 'Email Alert to Team'.")

    pdf.add_section_heading("3. Tab 2: New Buildings (UAE & India Permits)")
    pdf.add_paragraph(
        "Tracks newly approved Building Permits, Green Building filings, RERA registrations, MoEFCC PARIVESH environmental clearances, and upcoming industrial/commercial projects across UAE and India."
    )
    pdf.add_subheading("A. Covered Municipalities & State Corporations")
    pdf.add_bullet("UAE Municipalities", "Dubai Municipality (DM / Trakhees / Al Sa'fat), Abu Dhabi DMT (MePS / DARI / KEZAD / Estidama), Sharjah Municipality, Ajman Municipality (AMPD), and Ras Al Khaimah (RAK Municipality Barjeel & RAKEZ).")
    pdf.add_bullet("Indian State Corporations", "Mumbai BMC / PMC Pune / MahaRERA / MIDC (Maharashtra), Bengaluru BBMP / KIADB (Karnataka), Kochi K-SMART / K-RERA (Kerala), Chennai GCC / CMDA / SIPCOT (Tamil Nadu), Hyderabad GHMC / TS-bPASS (Telangana), Delhi NCR / Noida / Gurugram, Ahmedabad AMC / GIDC (Gujarat), and All-India MoEFCC PARIVESH.")

    pdf.add_subheading("B. Key Details Shown on Every Building Permit Card")
    pdf.add_bullet("Permit No. & Date", "Official or indexed permit reference number, approval status, and application/permit date.")
    pdf.add_bullet("ProjectStakeholders", "1) Client / Developer / Owner Name, 2) Engineering / MEP / Lead Consultant Name, and 3) Main / MEP Contractor Name.")
    pdf.add_bullet("Client & Project Contact Details", "Contact Person, Email Address, Phone/WhatsApp number, and project location.")
    pdf.add_bullet("Actions", "Click 'Scan UAE & India Municipalities Now' to fetch new projects, '+ Add Building Permit' to log a permit manually, 'Export Permits to CSV' to download an Excel/CSV report, or 'Send Project to +918138858961 (WhatsApp)'.")

    pdf.add_section_heading("4. Tab 3: Search Previous Enquiries (DB)")
    pdf.add_paragraph(
        "Allows you to search and audit your entire historical PostgreSQL database of past enquiries at any time:"
    )
    pdf.add_bullet("Multi-Criteria Search", "Filter by Keyword/Company/POC Name/Phone/Email, Service Activity, Region (UAE, KSA, India), Source Platform, From Date, To Date, Minimum AI Score, and POC Availability.")
    pdf.add_bullet("CSV Export", "Click 'Export Results to CSV' to download all matching historical enquiries into a spreadsheet.")

    pdf.add_section_heading("5. Tab 4: Team Numbers & Emails Config")
    pdf.add_paragraph(
        "Manage all phone numbers and email addresses that receive automated alerts from the AI Watcher:"
    )
    pdf.add_bullet("Pre-Configured Number", "Your Indian WhatsApp number (+918138858961) is pre-loaded and active by default.")
    pdf.add_bullet("Add a New Number or Email", "Enter Team Member Name, Role, WhatsApp Number (with country code, e.g. +91... or +971...), Email Address, and Region Filter (All Regions, India Only, UAE Only, or KSA Only), then click 'Save Contact to Database'.")
    pdf.add_bullet("Edit, Test, or Delete", "Use 'Edit' to modify any existing number/email, 'Test WA' / 'Test Email' to send a verification alert to that specific person, or 'Delete' to remove them.")

    pdf.add_section_heading("6. Tab 5: Live AI Enquiry Analyzer")
    pdf.add_paragraph(
        "A sandbox where you can paste any LinkedIn post, tender notice, or WhatsApp message to test how the SETS AI Engine scores it:"
    )
    pdf.add_bullet("Anti-Duplication Verification", "Checks if a similar enquiry already exists in your database and displays a warning banner if it is a duplicate.")
    pdf.add_bullet("POC & Pitch Extraction", "Extracts Contact Name, Role, Organization, Email, Phone, and generates a custom SETS sales pitch.")

    pdf.add_section_heading("7. Tab 6: PostgreSQL, LinkedIn & WhatsApp Settings")
    pdf.add_bullet("Free PostgreSQL Configuration", "Enter your Neon.tech, Supabase, or Local PostgreSQL URI and click 'Test & Connect PostgreSQL'.")
    pdf.add_bullet("Open-Source WhatsApp Configuration", "Select between SETS Open-Source Local Bridge (Baileys), WAHA, CallMeBot, Meta Cloud API, or Twilio, and click 'Send Test WhatsApp to +918138858961'.")
    pdf.add_bullet("Direct LinkedIn Server Cookie & Gemini Key", "Optionally paste your LinkedIn 'li_at' session cookie for authenticated LinkedIn searches and your Google Gemini API key. All secrets are encrypted with Windows 64-Bit DPAPI.")
    pdf.add_bullet("Anti-Duplication Threshold", "Adjust the similarity cutoff (default 0.62 = blocks enquiries that are >= 62% similar to existing database records).")

    pdf.add_section_heading("8. Tab 7: Security Shield & Android Phone Sync")
    pdf.add_bullet("Multi-Layer Defense Against Outside Attacks", "Includes App PIN Vault Lock (default PIN: 2026) with 5-attempt Brute-Force Lockout, Android FLAG_SECURE anti-screenshot / anti-screen-recording guard, Root/Debugger detection, and AES-256 credential encryption.")
    pdf.add_bullet("Android Phone Bottom Navigation Bar", "On Android phone displays, a thumb-friendly 5-button Bottom Navigation Bar (Enquiries, Buildings, DB Search, Contacts, More/Shield) and One-Tap Call / WhatsApp / Email buttons adapt automatically to your phone screen.")
    pdf.add_bullet("Autonomous On-Phone Engine vs. PC Server Sync", "Choose 'Standalone On-Phone Engine' to run 100% on your phone, or enter your PC/Cloud Server URL + API Token to sync live.")

    pdf.add_section_heading("9. Tab 8: Scan & Alert Logs")
    pdf.add_bullet("Recent Internet Scan Runs", "Shows every scheduled and manual scan, how many posts were found, how many duplicates were blocked, and how many new unique leads were saved.")
    pdf.add_bullet("Notification Dispatch Audit Log", "Shows the delivery status and timestamp of every WhatsApp and Email alert sent to your team.")

    pdf.save(output_path)


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    install_pdf = os.path.join(base_dir, "SETS_How_To_Install_Guide.pdf")
    usage_pdf = os.path.join(base_dir, "SETS_How_To_Use_User_Manual.pdf")
    build_installation_guide_pdf(install_pdf)
    build_user_manual_pdf(usage_pdf)
    print(f"Generated PDF 1: {install_pdf}")
    print(f"Generated PDF 2: {usage_pdf}")

