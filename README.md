# SETS AI Lead Watcher (`www.sets4us.com`)

An always-on **AI Internet & Social Media Enquiry Watcher** tailored for **SETS (`www.sets4us.com`)** across **UAE, Saudi Arabia (KSA), and India** with **PostgreSQL Database**, **Semantic Anti-Duplication**, **Historical Enquiry Search**, **Open-Source WhatsApp Bridge (`+918138858961`)**, and a **Team Numbers & Emails Configuration Manager**.

---

## Key Features

### 1. Free PostgreSQL Database Engine ([`watcher/database.py`](file:///d:/PYTHON/MARKET/watcher/database.py))
- Supports **Free Cloud PostgreSQL** (**Neon.tech Free Tier**, **Supabase Free Tier**, **Aiven Free Tier**) and **Local PostgreSQL** (`postgresql://postgres:postgres@localhost:5432/sets_watcher`).
- Run [`setup_postgres.bat`](file:///d:/PYTHON/MARKET/setup_postgres.bat) once to install the Python PostgreSQL drivers (`psycopg2-binary` and `pg8000`), then paste your PostgreSQL connection string in the **⚙️ PostgreSQL, WhatsApp & AI Settings** tab and click **🔌 Test & Connect PostgreSQL**.
- Includes an automatic local SQL cache (`data/sets_watcher_pgcache.db`) so the application works immediately even while offline or before connecting your PostgreSQL instance.

### 2. Multi-Layer Semantic Anti-Duplication Engine ([`check_duplicate_or_similar_lead`](file:///d:/PYTHON/MARKET/watcher/database.py#L283-L365))
- Every incoming enquiry is compared against existing enquiries in the database before saving or notifying:
  1. **Canonical URL Check**: Strips tracking query parameters (`?utm_*`, `trk=`) and blocks reposted URLs.
  2. **Normalized Token Fingerprint**: Removes stopwords and word-order variations.
  3. **Fuzzy & Jaccard Similarity Check**: Blocks slightly reworded or reposted enquiries above the configurable similarity threshold (default `0.62` / `62%` similarity).
  4. **Same Point-of-Contact Check**: Blocks duplicate enquiries from the same email or phone number within the same service category.

### 3. Historical Database Enquiry Search (`🗄️ Search Previous Enquiries (DB)` Tab)
- Search any previous enquiry stored in the database by **Keyword / Company / POC Name / POC Phone / POC Email**, **Service Activity**, **Region (`UAE`, `KSA`, `India`)**, **Platform**, **Date Range (`From Date` – `To Date`)**, **Minimum AI Score**, and **POC Availability**.
- Includes one-click **📥 Export Results to CSV**.

### 4. Open-Source Free WhatsApp API Pre-Configured for `+918138858961`
- Pre-configured with your Indian WhatsApp number **`+918138858961`** in [`watcher/config.py`](file:///d:/PYTHON/MARKET/watcher/config.py) and the `team_contacts` table.
- Includes a complete **Self-Hosted Open-Source Node.js WhatsApp Bridge** ([`whatsapp_bridge/server.js`](file:///d:/PYTHON/MARKET/whatsapp_bridge/server.js)) powered by `@whiskeysockets/baileys` (100% free, open-source MIT license, no per-message cost):
  1. Double-click [`start_whatsapp_bridge.bat`](file:///d:/PYTHON/MARKET/start_whatsapp_bridge.bat).
  2. It opens `http://127.0.0.1:3001` showing a QR code — scan it once from WhatsApp (**Linked Devices → Link a Device**).
  3. The watcher will automatically send all qualified lead alerts directly to **`+918138858961`** and all active team numbers!
- Also supports **WAHA (Open-Source WhatsApp HTTP API)**, **CallMeBot Free WhatsApp Bot**, **Meta Cloud API**, and **Twilio**.

### 5. Team Numbers & Emails Configuration Page (`👥 Team Numbers & Emails Config` Tab)
- **Add**, **Edit**, **Delete**, or **Pause** any team member's WhatsApp phone number or email address directly in the UI.
- Filter alerts per recipient by region (`All Regions`, `India Only`, `UAE Only`, `KSA Only`) and test any individual number or email with one click.

---

## Quick Start

1. **Start the Main AI Watcher Dashboard**:
   Double-click [`run.bat`](file:///d:/PYTHON/MARKET/run.bat) (opens `http://127.0.0.1:8080`).
2. **Start the Free Open-Source WhatsApp Bridge (Optional, for automated WhatsApp delivery to `+918138858961`)**:
   Double-click [`start_whatsapp_bridge.bat`](file:///d:/PYTHON/MARKET/start_whatsapp_bridge.bat) (opens `http://127.0.0.1:3001` to link WhatsApp).
3. **Install PostgreSQL Drivers (Optional, when connecting to Local or Cloud PostgreSQL)**:
   Double-click [`setup_postgres.bat`](file:///d:/PYTHON/MARKET/setup_postgres.bat).
