/**
 * SETS AI Lead Watcher - Frontend Logic (www.sets4us.com)
 * Includes:
 * 1. Live Enquiries Feed + On-Demand Live LinkedIn Server & Web Keyword Search
 * 2. New Buildings Tab (UAE & Indian Municipal Building Permits & Industrial Projects with Client/Consultant/Contractor)
 * 3. Historical Database Enquiry Search & CSV Export
 * 4. Team WhatsApp Numbers (+918138858961) & Email Contacts Manager
 * 5. PostgreSQL Connection Manager, LinkedIn Cookie & Open-Source WhatsApp Bridge Config
 */

let currentCategory = "ALL";
let cachedLeads = [];
let cachedBuildings = [];
let archiveResults = [];
let teamContacts = [];

function showToast(msg, isError = false) {
  const el = document.getElementById("toastBanner");
  el.textContent = msg;
  el.className = isError ? "toast error" : "toast";
  el.classList.remove("hidden");
  setTimeout(() => {
    el.classList.add("hidden");
  }, 6500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabName}`);
  });
  // Update Android Bottom Navigation Bar active state
  const primaryBottomTabs = ["leads", "buildings", "archive", "contacts"];
  document.querySelectorAll("#mobileBottomNav .bnav-item").forEach((b) => {
    if (primaryBottomTabs.includes(tabName)) {
      b.classList.toggle("active", b.dataset.bnav === tabName);
    } else {
      b.classList.toggle("active", b.dataset.bnav === "more");
    }
  });
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (tabName === "leads") {
    loadOverview();
    loadLeads();
  } else if (tabName === "buildings") {
    loadBuildingPermits();
  } else if (tabName === "archive") {
    runArchiveSearch();
  } else if (tabName === "contacts") {
    loadContactsTable();
  } else if (tabName === "settings") {
    loadSettingsForm();
  } else if (tabName === "security") {
    if (window.SETSMobileSecurity) {
      window.SETSMobileSecurity.renderSecurityCenter();
    }
  } else if (tabName === "logs") {
    loadLogs();
  }
}

function toggleMobileMoreSheet() {
  const sheet = document.getElementById("mobileMoreSheet");
  if (sheet) sheet.classList.toggle("hidden");
}

function closeMobileMoreSheet() {
  const sheet = document.getElementById("mobileMoreSheet");
  if (sheet) sheet.classList.add("hidden");
}

function switchTabFromSheet(tabName) {
  closeMobileMoreSheet();
  switchTab(tabName);
}

function appendPinDigit(digit) {
  const inp = document.getElementById("pinUnlockInput");
  if (!inp) return;
  if (digit === "CLR") {
    inp.value = "";
  } else if (inp.value.length < 8) {
    inp.value += digit;
  }
}

function selectCategoryPill(cat) {
  currentCategory = cat;
  document.querySelectorAll("#categoryPills .pill").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.cat === cat);
  });
  loadLeads();
}

async function loadOverview() {
  try {
    const res = await fetch("/api/overview");
    const data = await res.json();
    const stats = data.stats || {};
    const watcher = data.watcher || {};

    document.getElementById("kpiTotal").textContent = stats.total_leads || 0;
    document.getElementById("kpiHighIntent").textContent = stats.high_intent_leads || 0;
    document.getElementById("kpiWithPoc").textContent = stats.leads_with_poc || 0;
    document.getElementById("kpiDuplicates").textContent = stats.duplicates_blocked || 0;

    const reg = stats.by_region || {};
    document.getElementById("kpiRegions").innerHTML = `
      <span>🇦🇪 UAE: ${reg["UAE"] || 0}</span>
      <span>🇸🇦 KSA: ${reg["KSA"] || 0}</span>
      <span>🇮🇳 India: ${reg["India"] || 0}</span>
    `;

    if (stats.db_status && stats.db_status.engine) {
      document.getElementById("kpiDbEngineText").textContent = stats.db_status.engine;
    }

    updateWatcherBanner(watcher);
  } catch (err) {
    console.error("Overview load error:", err);
  }
}

function updateWatcherBanner(watcher) {
  const badge = document.getElementById("watcherBadge");
  const statusText = document.getElementById("watcherStatusText");
  const stageText = document.getElementById("watcherStageText");
  const btn = document.getElementById("btnScanNow");

  if (watcher.is_scanning) {
    badge.className = "status-pill status-scanning";
    statusText.textContent = "Scanning Internet...";
    stageText.textContent = watcher.current_stage || "Running rotating queries...";
    btn.disabled = true;
    btn.textContent = "⏳ Scanning...";
  } else {
    badge.className = "status-pill status-active";
    statusText.textContent = watcher.watcher_enabled
      ? `Watcher Active (Every ${watcher.scan_interval_minutes || 30}m)`
      : "Watcher Paused";
    if (watcher.last_result && watcher.last_result.details) {
      stageText.textContent = watcher.last_result.details;
    } else {
      stageText.textContent = "Monitoring UAE, KSA & India";
    }
    btn.disabled = false;
    btn.textContent = "🔍 Scan Rotating Queries Now";
  }
}

async function triggerScanNow() {
  try {
    const res = await fetch("/api/scan/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sync: false }),
    });
    const data = await res.json();
    showToast(data.message || "Rotating LinkedIn, Web & Municipal scan launched!");
    loadOverview();
  } catch (err) {
    showToast("Failed to trigger scan: " + err.message, true);
  }
}

// ============================================================================
// ON-DEMAND LIVE LINKEDIN SERVER & INTERNET KEYWORD SEARCH
// ============================================================================

async function runLiveKeywordSearchUI() {
  const kwInput = document.getElementById("liveSearchKeyword");
  const keyword = kwInput.value.trim();
  const region = document.getElementById("liveSearchRegion").value;
  const category = document.getElementById("liveSearchCategory").value;
  const btn = document.getElementById("btnLiveSearch");

  if (!keyword) {
    showToast("Please enter a keyword (e.g. 'BMS tender Dubai' or 'Energy Audit Mumbai') to search live.", true);
    return;
  }

  btn.disabled = true;
  btn.textContent = "⏳ Searching LinkedIn & Web...";
  try {
    const res = await fetch("/api/search/live", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, region, category }),
    });
    const data = await res.json();
    if (!data.ok) {
      showToast(data.error || "Live search failed", true);
    } else {
      showToast(
        `Live Search for "${keyword}" (${region}): Scanned ${data.raw_found} live results, saved ${data.new_saved} new unique enquiries (${data.duplicates_blocked} duplicates skipped)!`
      );
      document.getElementById("filterSearch").value = "";
      currentCategory = "ALL";
      document.querySelectorAll("#categoryPills .pill").forEach((b) => {
        b.classList.toggle("active", b.dataset.cat === "ALL");
      });
      await loadLeads();
      await loadOverview();
    }
  } catch (err) {
    showToast("Live search error: " + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "🔎 Fetch Live LinkedIn & Web Results";
  }
}

function buildDirectWhatsAppUrl(lead, targetPhone = "918138858961") {
  const services = Array.isArray(lead.matched_services)
    ? lead.matched_services.join(", ")
    : lead.category;
  const text =
    `🚨 *SETS AI Lead Alert (www.sets4us.com)*\n\n` +
    `*Enquiry:* ${lead.title}\n` +
    `*Services:* ${services}\n` +
    `*Region:* ${lead.region} | *Score:* ${lead.relevance_score}/100 (${lead.urgency})\n\n` +
    `*Summary:* ${lead.ai_summary}\n\n` +
    `*Point of Contact (POC):*\n` +
    `• Name: ${lead.poc_name || "—"}\n` +
    `• Role/Org: ${[lead.poc_role, lead.poc_company].filter(Boolean).join(" - ") || "—"}\n` +
    `• Email: ${lead.poc_email || "—"}\n` +
    `• Phone: ${lead.poc_phone || "—"}\n\n` +
    `*Source:* ${lead.url}`;
  const cleanTarget = String(targetPhone || "").replace(/[^0-9]/g, "");
  return `https://wa.me/${cleanTarget}?text=${encodeURIComponent(text)}`;
}

async function loadLeads() {
  const region = document.getElementById("filterRegion").value;
  const platform = document.getElementById("filterPlatform").value;
  const status = document.getElementById("filterStatus").value;
  const q = document.getElementById("filterSearch").value;

  const params = new URLSearchParams({
    category: currentCategory,
    region,
    platform,
    status,
    q,
  });

  try {
    const res = await fetch(`/api/leads?${params.toString()}`);
    const data = await res.json();
    cachedLeads = data.leads || [];
    renderLeads(cachedLeads);
  } catch (err) {
    console.error("Failed loading leads:", err);
  }
}

function renderLeads(leads) {
  const container = document.getElementById("leadsList");
  if (!leads.length) {
    container.innerHTML = `
      <div class="panel-card" style="text-align:center; padding: 40px;">
        <h3>No matching enquiries found for the current filter</h3>
        <p class="muted-text" style="margin-top:8px;">
          Use the <strong>"🌐 Live On-Demand LinkedIn Server &amp; Internet Requirement Search"</strong> bar above or click <strong>"🔍 Scan Rotating Queries Now"</strong>.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = leads
    .map((lead) => {
      const services = Array.isArray(lead.matched_services)
        ? lead.matched_services
        : [lead.category];
      const serviceBadges = services
        .map((s) => `<span class="badge badge-cat">${escapeHtml(s)}</span>`)
        .join("");

      const scoreClass =
        lead.relevance_score >= 75 ? "badge-score-high" : "badge-score-med";
      const waDirectUrl = buildDirectWhatsAppUrl(lead, "918138858961");

      return `
      <div class="lead-card">
        <div class="lead-header">
          <div class="badge-row">
            ${serviceBadges}
            <span class="badge badge-region">🌍 ${escapeHtml(lead.region)}</span>
            <span class="badge badge-platform">📡 ${escapeHtml(lead.source_platform)}</span>
            <span class="badge ${scoreClass}">🎯 AI Score: ${lead.relevance_score}/100 (${escapeHtml(lead.urgency)})</span>
          </div>
          <div>
            <select class="input-control" style="padding: 4px 10px; font-size: 12px; width: auto;" onchange="changeLeadStatus(${lead.id}, this.value)">
              ${["New", "Contacted", "Qualified", "Proposal Sent", "Archived"]
                .map(
                  (st) =>
                    `<option value="${st}" ${lead.status === st ? "selected" : ""}>${st}</option>`
                )
                .join("")}
            </select>
          </div>
        </div>

        <div class="lead-title">
          <a href="${escapeHtml(lead.url)}" target="_blank" rel="noopener">
            #${lead.id} — ${escapeHtml(lead.title)} ↗
          </a>
        </div>

        <div class="lead-summary">
          <strong>AI Assessment:</strong> ${escapeHtml(lead.ai_summary)}
        </div>

        <div class="lead-snippet">
          ${escapeHtml(lead.snippet)}
        </div>

        <div class="lead-grid-boxes">
          <div class="poc-box">
            <div class="poc-box-title">👤 Extracted Point of Contact (POC)</div>
            <div class="poc-grid">
              <div class="poc-item"><strong>Name:</strong> ${escapeHtml(lead.poc_name || "See Source Post")}</div>
              <div class="poc-item"><strong>Role:</strong> ${escapeHtml(lead.poc_role || "—")}</div>
              <div class="poc-item"><strong>Company:</strong> ${escapeHtml(lead.poc_company || "—")}</div>
              <div class="poc-item"><strong>Location:</strong> ${escapeHtml(lead.poc_location || lead.region)}</div>
              <div class="poc-item">
                <strong>Email:</strong>
                ${
                  lead.poc_email
                    ? `<a href="mailto:${escapeHtml(lead.poc_email)}">${escapeHtml(lead.poc_email)}</a>`
                    : "—"
                }
              </div>
              <div class="poc-item">
                <strong>Phone/WA:</strong>
                ${
                  lead.poc_phone
                    ? `<a href="https://wa.me/${lead.poc_phone.replace(/[^0-9]/g, "")}" target="_blank">${escapeHtml(lead.poc_phone)}</a>`
                    : "—"
                }
              </div>
            </div>
          </div>

          <div class="pitch-box">
            <div>
              <div class="pitch-box-title">💬 Suggested SETS Outreach Pitch</div>
              <div id="pitch-${lead.id}">${escapeHtml(lead.suggested_pitch)}</div>
            </div>
            <div style="margin-top: 8px; text-align: right;">
              <button class="btn btn-secondary btn-sm" onclick="copyPitchText(${lead.id})">
                📋 Copy Pitch
              </button>
            </div>
          </div>
        </div>

        <div class="lead-footer">
          <div class="btn-group">
            <button class="btn btn-whatsapp btn-sm" onclick="notifyTeamForLead(${lead.id}, 'whatsapp')">
              💬 WA Alert ${lead.notified_whatsapp ? "✓" : ""}
            </button>
            <a href="${waDirectUrl}" target="_blank" rel="noopener" class="btn btn-whatsapp btn-sm">
              📲 Send to +918138858961
            </a>
            ${
              lead.poc_phone
                ? `<a href="tel:${escapeHtml(lead.poc_phone.replace(/[^+0-9]/g, ""))}" class="btn btn-secondary btn-sm">📞 Call POC</a>`
                : ""
            }
            <button class="btn btn-email btn-sm" onclick="notifyTeamForLead(${lead.id}, 'email')">
              📧 Email Alert ${lead.notified_email ? "✓" : ""}
            </button>
            <a href="${escapeHtml(lead.url)}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
              🔗 Source
            </a>
          </div>
          <div style="display:flex; align-items:center; gap: 10px;">
            <span style="font-size:11.5px; color:#64748b;">Discovered: ${escapeHtml((lead.discovered_at || "").slice(0, 10))}</span>
            <button class="btn btn-danger btn-sm" onclick="removeLead(${lead.id})">🗑️</button>
          </div>
        </div>
      </div>
    `;
    })
    .join("");
}

// ============================================================================
// TAB 2: NEW BUILDINGS (UAE & INDIA MUNICIPAL BUILDING PERMITS & PROJECTS)
// ============================================================================

async function loadBuildingPermits() {
  const q = document.getElementById("bldgSearch").value.trim();
  const country = document.getElementById("bldgCountry").value;
  const municipality = document.getElementById("bldgMunicipality").value;
  const project_type = document.getElementById("bldgType").value;

  const params = new URLSearchParams({
    q,
    country,
    municipality,
    project_type,
  });

  try {
    const res = await fetch(`/api/buildings?${params.toString()}`);
    const data = await res.json();
    cachedBuildings = data.permits || [];
    document.getElementById("buildingsCountLabel").textContent =
      `Showing ${cachedBuildings.length} Building & Industrial Permit Projects (UAE & India Municipalities)`;
    renderBuildingPermits(cachedBuildings);
  } catch (err) {
    console.error("Failed loading building permits:", err);
  }
}

function buildBuildingWhatsAppUrl(b) {
  const services = Array.isArray(b.sets_services)
    ? b.sets_services.join(", ")
    : "BMS, CMS, Energy Audit";
  const text =
    `🏗️ *SETS New Building / Industrial Permit Alert (www.sets4us.com)*\n\n` +
    `*Permit No:* ${b.permit_number} (${b.permit_date})\n` +
    `*Municipality:* ${b.municipality}\n` +
    `*Project:* ${b.project_title}\n` +
    `*Type:* ${b.project_type} | *Location:* ${b.location}\n\n` +
    `*Project Stakeholders & Contacts:*\n` +
    `• *Client / Developer:* ${b.client_name}\n` +
    `• *Engineering / MEP Consultant:* ${b.consultant_name}\n` +
    `• *Main / MEP Contractor:* ${b.contractor_name}\n` +
    `• *Contact Person:* ${b.contact_person || "—"}\n` +
    `• *Email:* ${b.contact_email || "—"}\n` +
    `• *Phone:* ${b.contact_phone || "—"}\n\n` +
    `*SETS Opportunity:* ${services}`;
  return `https://wa.me/918138858961?text=${encodeURIComponent(text)}`;
}

function renderBuildingPermits(permits) {
  const container = document.getElementById("buildingsListContainer");
  if (!permits.length) {
    container.innerHTML = `
      <div class="panel-card" style="text-align:center; padding: 36px;">
        <h3>No building permits matched the current filter</h3>
        <p class="muted-text" style="margin-top:8px;">
          Click <strong>"🔄 Scan UAE &amp; India Municipalities Now"</strong> above to fetch new building permits and upcoming industrial projects.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = permits
    .map((b) => {
      const services = Array.isArray(b.sets_services)
        ? b.sets_services
        : ["BMS", "CMS", "Energy Audit"];
      const serviceBadges = services
        .map((s) => `<span class="badge badge-cat">${escapeHtml(s)}</span>`)
        .join("");
      const waUrl = buildBuildingWhatsAppUrl(b);

      return `
      <div class="lead-card">
        <div class="lead-header">
          <div class="badge-row">
            <span class="badge badge-score-high">📜 Permit: ${escapeHtml(b.permit_number)}</span>
            <span class="badge badge-region">🏛️ ${escapeHtml(b.municipality)}</span>
            <span class="badge badge-platform">🏢 ${escapeHtml(b.project_type)}</span>
            <span class="badge badge-score-med">📅 Date: ${escapeHtml(b.permit_date)}</span>
            ${serviceBadges}
          </div>
          <div>
            <span class="badge badge-cat">${escapeHtml(b.permit_status)}</span>
          </div>
        </div>

        <div class="lead-title">
          <a href="${escapeHtml(b.source_url || "#")}" target="_blank" rel="noopener">
            ${escapeHtml(b.project_title)} (${escapeHtml(b.location)}) ↗
          </a>
        </div>

        <div class="lead-summary">
          <strong>Scope &amp; Green Building Code:</strong> ${escapeHtml(b.description)}
        </div>

        <div class="lead-grid-boxes">
          <div class="poc-box">
            <div class="poc-box-title">🏗️ Client, Consultant &amp; Contractor Details</div>
            <div class="poc-grid" style="grid-template-columns: 1fr;">
              <div class="poc-item"><strong>🏛️ Client / Owner:</strong> <span style="color:#34d399; font-weight:700;">${escapeHtml(b.client_name)}</span></div>
              <div class="poc-item"><strong>📐 Consultant (Lead / MEP):</strong> <span style="color:#38bdf8; font-weight:600;">${escapeHtml(b.consultant_name)}</span></div>
              <div class="poc-item"><strong>👷 Contractor (Main / MEP):</strong> <span style="color:#fbbf24; font-weight:600;">${escapeHtml(b.contractor_name)}</span></div>
            </div>
          </div>

          <div class="poc-box">
            <div class="poc-box-title">📞 Project Point of Contact (POC)</div>
            <div class="poc-grid">
              <div class="poc-item"><strong>Contact Person:</strong> ${escapeHtml(b.contact_person || "Project Desk")}</div>
              <div class="poc-item"><strong>Location:</strong> ${escapeHtml(b.location)}</div>
              <div class="poc-item">
                <strong>Email:</strong>
                ${
                  b.contact_email
                    ? `<a href="mailto:${escapeHtml(b.contact_email)}">${escapeHtml(b.contact_email)}</a>`
                    : "—"
                }
              </div>
              <div class="poc-item">
                <strong>Phone/WA:</strong>
                ${
                  b.contact_phone
                    ? `<a href="https://wa.me/${b.contact_phone.replace(/[^0-9]/g, "")}" target="_blank">${escapeHtml(b.contact_phone)}</a>`
                    : "—"
                }
              </div>
            </div>
          </div>
        </div>

        <div class="lead-footer">
          <div class="btn-group">
            <a href="${waUrl}" target="_blank" rel="noopener" class="btn btn-whatsapp btn-sm">
              📲 Send to +918138858961 (WA)
            </a>
            ${
              b.contact_phone
                ? `<a href="tel:${escapeHtml(b.contact_phone.replace(/[^+0-9]/g, ""))}" class="btn btn-secondary btn-sm">📞 Call Contact</a>`
                : ""
            }
            ${
              b.contact_email
                ? `<a href="mailto:${escapeHtml(b.contact_email)}?subject=${encodeURIComponent("SETS Engineering & Sustainability Proposal - " + b.project_title)}" class="btn btn-email btn-sm">📧 Email Client/Consultant</a>`
                : ""
            }
            <a href="${escapeHtml(b.source_url || "#")}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
              🏛️ Source Portal
            </a>
          </div>
          <button class="btn btn-danger btn-sm" onclick="removeBuildingPermit(${b.id})">🗑️</button>
        </div>
      </div>
      `;
    })
    .join("");
}

async function scanMunicipalBuildingPermits() {
  const btn = document.getElementById("btnScanBuildings");
  const country = document.getElementById("bldgCountry").value;
  const municipality = document.getElementById("bldgMunicipality").value;

  btn.disabled = true;
  btn.textContent = "⏳ Scanning Municipalities...";
  try {
    const res = await fetch("/api/buildings/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country, municipality }),
    });
    const data = await res.json();
    showToast(data.message || "Municipal building permit scan complete!");
    await loadBuildingPermits();
  } catch (err) {
    showToast("Municipal scan failed: " + err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "🔄 Scan UAE & India Municipalities Now";
  }
}

function toggleAddBuildingModal() {
  const box = document.getElementById("addBuildingBox");
  box.classList.toggle("hidden");
  if (!document.getElementById("bpDate").value) {
    document.getElementById("bpDate").value = new Date().toISOString().slice(0, 10);
  }
}

async function saveNewBuildingPermit() {
  const payload = {
    permit_number: document.getElementById("bpNumber").value.trim() || "BP-2026-NEW",
    permit_date: document.getElementById("bpDate").value || new Date().toISOString().slice(0, 10),
    country: document.getElementById("bpCountry").value,
    municipality: document.getElementById("bpMunicipality").value,
    location: document.getElementById("bpMunicipality").value,
    project_title: document.getElementById("bpTitle").value.trim(),
    project_type: document.getElementById("bpType").value,
    client_name: document.getElementById("bpClient").value.trim(),
    consultant_name: document.getElementById("bpConsultant").value.trim(),
    contractor_name: document.getElementById("bpContractor").value.trim(),
    contact_person: document.getElementById("bpContactPerson").value.trim(),
    contact_email: document.getElementById("bpEmail").value.trim(),
    contact_phone: document.getElementById("bpPhone").value.trim(),
    description: "Added building permit project requiring SETS BMS, CMS, Energy Audit & Sustainability services.",
    sets_services: ["BMS", "CMS", "Energy Audit", "Sustainability Audit"],
  };

  if (!payload.project_title || !payload.client_name) {
    showToast("Please enter at least the Project Title and Client Name.", true);
    return;
  }

  try {
    const res = await fetch("/api/buildings/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      showToast("New building permit project saved to database!");
      toggleAddBuildingModal();
      loadBuildingPermits();
    } else {
      showToast(data.duplicate_reason || "Duplicate project already exists.", true);
    }
  } catch (err) {
    showToast("Error saving building permit: " + err.message, true);
  }
}

async function removeBuildingPermit(id) {
  await fetch("/api/buildings/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  loadBuildingPermits();
}

function exportBuildingsCsv() {
  if (!cachedBuildings.length) {
    showToast("No building permits to export.", true);
    return;
  }
  const headers = [
    "Permit_Number",
    "Permit_Date",
    "Country",
    "Municipality",
    "Location",
    "Project_Title",
    "Project_Type",
    "Client_Name",
    "Consultant_Name",
    "Contractor_Name",
    "Contact_Person",
    "Contact_Email",
    "Contact_Phone",
    "Status",
  ];
  const rows = [headers.join(",")];
  for (const b of cachedBuildings) {
    const vals = [
      `"${String(b.permit_number || "").replace(/"/g, '""')}"`,
      b.permit_date,
      b.country,
      `"${String(b.municipality || "").replace(/"/g, '""')}"`,
      `"${String(b.location || "").replace(/"/g, '""')}"`,
      `"${String(b.project_title || "").replace(/"/g, '""')}"`,
      `"${String(b.project_type || "").replace(/"/g, '""')}"`,
      `"${String(b.client_name || "").replace(/"/g, '""')}"`,
      `"${String(b.consultant_name || "").replace(/"/g, '""')}"`,
      `"${String(b.contractor_name || "").replace(/"/g, '""')}"`,
      `"${String(b.contact_person || "").replace(/"/g, '""')}"`,
      `"${String(b.contact_email || "").replace(/"/g, '""')}"`,
      `"${String(b.contact_phone || "").replace(/"/g, '""')}"`,
      `"${String(b.permit_status || "").replace(/"/g, '""')}"`,
    ];
    rows.push(vals.join(","));
  }
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `sets_building_permits_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
}

// ============================================================================
// TAB 3: DATABASE ARCHIVE & HISTORICAL ENQUIRY SEARCH
// ============================================================================

async function runArchiveSearch() {
  const q = document.getElementById("archQuery").value.trim();
  const category = document.getElementById("archCategory").value;
  const region = document.getElementById("archRegion").value;
  const platform = document.getElementById("archPlatform").value;
  const date_from = document.getElementById("archDateFrom").value;
  const date_to = document.getElementById("archDateTo").value;
  const min_score = document.getElementById("archMinScore").value || "0";
  const has_poc = document.getElementById("archHasPoc").value;

  const params = new URLSearchParams({
    q,
    category,
    region,
    platform,
    date_from,
    date_to,
    min_score,
    has_poc,
    limit: "500",
  });

  try {
    const res = await fetch(`/api/leads?${params.toString()}`);
    const data = await res.json();
    archiveResults = data.leads || [];
    document.getElementById("archiveResultCount").textContent =
      `Found ${archiveResults.length} historical enquiries matching your database search criteria.`;
    renderArchiveTable(archiveResults);
  } catch (err) {
    console.error("Archive search error:", err);
  }
}

function resetArchiveFilters() {
  document.getElementById("archQuery").value = "";
  document.getElementById("archCategory").value = "ALL";
  document.getElementById("archRegion").value = "ALL";
  document.getElementById("archPlatform").value = "ALL";
  document.getElementById("archDateFrom").value = "";
  document.getElementById("archDateTo").value = "";
  document.getElementById("archMinScore").value = "0";
  document.getElementById("archHasPoc").value = "ALL";
  runArchiveSearch();
}

function renderArchiveTable(rows) {
  const wrap = document.getElementById("archiveTableContainer");
  if (!rows.length) {
    wrap.innerHTML = `<p class="muted-text" style="padding: 20px 0;">No previous enquiries matched your search filters.</p>`;
    return;
  }

  wrap.innerHTML = `
    <table class="logs-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Date</th>
          <th>Region</th>
          <th>Activity</th>
          <th>Score</th>
          <th>Enquiry Title &amp; Summary</th>
          <th>Point of Contact (POC)</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((r) => {
            const waUrl = buildDirectWhatsAppUrl(r, "918138858961");
            return `
            <tr>
              <td><strong>#${r.id}</strong></td>
              <td style="white-space:nowrap;">${escapeHtml((r.discovered_at || "").slice(0, 10))}</td>
              <td><span class="badge badge-region">${escapeHtml(r.region)}</span></td>
              <td><span class="badge badge-cat">${escapeHtml(r.category)}</span></td>
              <td><strong>${r.relevance_score}%</strong></td>
              <td style="max-width:340px;">
                <div style="font-weight:700; color:#f8fafc;">
                  <a href="${escapeHtml(r.url)}" target="_blank" style="color:#34d399; text-decoration:none;">
                    ${escapeHtml(r.title)} ↗
                  </a>
                </div>
                <div style="font-size:11.5px; color:#94a3b8; margin-top:3px;">
                  ${escapeHtml(r.ai_summary)}
                </div>
              </td>
              <td style="font-size:12px;">
                <div><strong>${escapeHtml(r.poc_name || "—")}</strong> ${r.poc_company ? `(${escapeHtml(r.poc_company)})` : ""}</div>
                <div>${escapeHtml(r.poc_email || "")} ${escapeHtml(r.poc_phone || "")}</div>
              </td>
              <td>${escapeHtml(r.status)}</td>
              <td style="white-space:nowrap;">
                <a href="${waUrl}" target="_blank" class="btn btn-whatsapp btn-sm">📲 WA</a>
                <button class="btn btn-danger btn-sm" onclick="removeLead(${r.id}); runArchiveSearch();">🗑️</button>
              </td>
            </tr>
          `;
          })
          .join("")}
      </tbody>
    </table>
  `;
}

function exportArchiveCsv() {
  if (!archiveResults.length) {
    showToast("No search results to export.", true);
    return;
  }
  const headers = [
    "ID",
    "Date",
    "Region",
    "Category",
    "Score",
    "Title",
    "POC_Name",
    "POC_Role",
    "POC_Company",
    "POC_Email",
    "POC_Phone",
    "Status",
    "URL",
  ];
  const csvRows = [headers.join(",")];
  for (const r of archiveResults) {
    const vals = [
      r.id,
      (r.discovered_at || "").slice(0, 10),
      r.region,
      r.category,
      r.relevance_score,
      `"${String(r.title || "").replace(/"/g, '""')}"`,
      `"${String(r.poc_name || "").replace(/"/g, '""')}"`,
      `"${String(r.poc_role || "").replace(/"/g, '""')}"`,
      `"${String(r.poc_company || "").replace(/"/g, '""')}"`,
      `"${String(r.poc_email || "").replace(/"/g, '""')}"`,
      `"${String(r.poc_phone || "").replace(/"/g, '""')}"`,
      r.status,
      `"${String(r.url || "").replace(/"/g, '""')}"`,
    ];
    csvRows.push(vals.join(","));
  }
  const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `sets_enquiries_export_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
}

// ============================================================================
// TAB 4: TEAM CONTACTS (ADD, EDIT, DELETE PHONE NUMBERS & EMAILS)
// ============================================================================

async function loadContactsTable() {
  try {
    const res = await fetch("/api/contacts");
    const data = await res.json();
    teamContacts = data.contacts || [];
    renderContactsTable(teamContacts);
  } catch (err) {
    console.error("Failed loading contacts:", err);
  }
}

function renderContactsTable(contacts) {
  const wrap = document.getElementById("contactsTableContainer");
  if (!contacts.length) {
    wrap.innerHTML = `<p class="muted-text">No team contacts configured yet. Add a phone number or email above.</p>`;
    return;
  }

  wrap.innerHTML = `
    <table class="logs-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Name &amp; Role</th>
          <th>WhatsApp Number</th>
          <th>Email Address</th>
          <th>Region Filter</th>
          <th>Channels Enabled</th>
          <th>Status</th>
          <th>Actions (Edit / Test / Delete)</th>
        </tr>
      </thead>
      <tbody>
        ${contacts
          .map(
            (c) => `
          <tr>
            <td>#${c.id}</td>
            <td>
              <strong>${escapeHtml(c.name)}</strong>
              <div style="font-size:11.5px; color:#94a3b8;">${escapeHtml(c.role || "")}</div>
            </td>
            <td>
              ${
                c.phone
                  ? `<span class="badge badge-cat">📱 ${escapeHtml(c.phone)}</span>`
                  : "—"
              }
            </td>
            <td>${escapeHtml(c.email || "—")}</td>
            <td><span class="badge badge-region">${escapeHtml(c.region_filter || "ALL")}</span></td>
            <td>
              ${c.notify_whatsapp ? '<span class="badge badge-score-high">WhatsApp ✓</span> ' : ""}
              ${c.notify_email ? '<span class="badge badge-platform">Email ✓</span>' : ""}
            </td>
            <td>
              ${
                c.active
                  ? '<span style="color:#34d399; font-weight:700;">● Active</span>'
                  : '<span style="color:#94a3b8;">Paused</span>'
              }
            </td>
            <td style="white-space:nowrap;">
              <button class="btn btn-secondary btn-sm" onclick="startEditContact(${c.id})">✏️ Edit</button>
              ${
                c.phone
                  ? `<button class="btn btn-whatsapp btn-sm" onclick="testSingleContact('whatsapp', '${escapeHtml(c.phone)}')">💬 Test WA</button>`
                  : ""
              }
              ${
                c.email
                  ? `<button class="btn btn-email btn-sm" onclick="testSingleContact('email', '${escapeHtml(c.email)}')">📧 Test Email</button>`
                  : ""
              }
              <button class="btn btn-danger btn-sm" onclick="deleteTeamContactRow(${c.id})">🗑️ Delete</button>
            </td>
          </tr>
        `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function startEditContact(id) {
  const c = teamContacts.find((x) => x.id === id);
  if (!c) return;
  document.getElementById("editContactId").value = String(c.id);
  document.getElementById("contactFormTitle").textContent = `✏️ Edit Team Contact #${c.id} (${c.name})`;
  document.getElementById("ctName").value = c.name || "";
  document.getElementById("ctRole").value = c.role || "";
  document.getElementById("ctPhone").value = c.phone || "";
  document.getElementById("ctEmail").value = c.email || "";
  document.getElementById("ctRegion").value = c.region_filter || "ALL";
  document.getElementById("ctNotifyWa").checked = Boolean(c.notify_whatsapp);
  document.getElementById("ctNotifyEmail").checked = Boolean(c.notify_email);
  document.getElementById("ctActive").checked = Boolean(c.active);
  document.getElementById("btnSaveContact").textContent = "💾 Update Contact";
  document.getElementById("btnCancelEditContact").classList.remove("hidden");
}

function resetContactForm() {
  document.getElementById("editContactId").value = "";
  document.getElementById("contactFormTitle").textContent = "➕ Add New Team Number / Email Contact";
  document.getElementById("ctName").value = "";
  document.getElementById("ctRole").value = "";
  document.getElementById("ctPhone").value = "";
  document.getElementById("ctEmail").value = "";
  document.getElementById("ctRegion").value = "ALL";
  document.getElementById("ctNotifyWa").checked = true;
  document.getElementById("ctNotifyEmail").checked = true;
  document.getElementById("ctActive").checked = true;
  document.getElementById("btnSaveContact").textContent = "💾 Save Contact to Database";
  document.getElementById("btnCancelEditContact").classList.add("hidden");
}

async function saveTeamContact() {
  const editId = document.getElementById("editContactId").value.trim();
  const payload = {
    id: editId ? parseInt(editId, 10) : undefined,
    name: document.getElementById("ctName").value.trim(),
    role: document.getElementById("ctRole").value.trim(),
    phone: document.getElementById("ctPhone").value.trim(),
    email: document.getElementById("ctEmail").value.trim(),
    region_filter: document.getElementById("ctRegion").value,
    notify_whatsapp: document.getElementById("ctNotifyWa").checked,
    notify_email: document.getElementById("ctNotifyEmail").checked,
    active: document.getElementById("ctActive").checked,
  };

  if (!payload.name) {
    showToast("Please enter a Team Member Name.", true);
    return;
  }
  if (!payload.phone && !payload.email) {
    showToast("Please provide at least a WhatsApp Phone Number or Email Address.", true);
    return;
  }

  const endpoint = editId ? "/api/contacts/update" : "/api/contacts/add";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    teamContacts = data.contacts || [];
    renderContactsTable(teamContacts);
    resetContactForm();
    showToast(editId ? "Team contact updated!" : "New team contact added to database!");
  } catch (err) {
    showToast("Error saving contact: " + err.message, true);
  }
}

async function deleteTeamContactRow(id) {
  try {
    const res = await fetch("/api/contacts/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const data = await res.json();
    teamContacts = data.contacts || [];
    renderContactsTable(teamContacts);
    showToast(`Contact #${id} deleted.`);
  } catch (err) {
    showToast("Error deleting contact: " + err.message, true);
  }
}

async function testSingleContact(channel, target) {
  try {
    const res = await fetch("/api/contacts/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, target }),
    });
    const data = await res.json();
    showToast(data.detail || "Test completed", !data.ok);
  } catch (err) {
    showToast("Test failed: " + err.message, true);
  }
}

// ============================================================================
// LEAD ACTIONS & ANALYZER
// ============================================================================

function copyPitchText(leadId) {
  const el = document.getElementById(`pitch-${leadId}`);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent.trim());
  showToast("Suggested SETS outreach pitch copied to clipboard!");
}

async function changeLeadStatus(leadId, status) {
  await fetch("/api/leads/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId, status }),
  });
  showToast(`Lead #${leadId} status updated to "${status}"`);
  loadOverview();
}

async function removeLead(leadId) {
  await fetch("/api/leads/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_id: leadId }),
  });
  loadLeads();
  loadOverview();
}

async function notifyTeamForLead(leadId, channel) {
  try {
    const res = await fetch("/api/leads/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lead_id: leadId, channel }),
    });
    const data = await res.json();
    const chResult = data.results && data.results[channel];
    if (chResult && chResult.ok) {
      showToast(chResult.detail);
      loadLeads();
      loadOverview();
    } else {
      showToast(
        (chResult && chResult.detail) ||
          "Check your WhatsApp Bridge / SMTP settings in the Settings tab.",
        true
      );
    }
  } catch (err) {
    showToast("Notification error: " + err.message, true);
  }
}

function fillSampleEnquiry() {
  document.getElementById("anTitle").value =
    "Urgent Requirement: ASHRAE Level 2 Energy Audit, BMS Retrofit & ESG Reporting for Industrial Facility in Dammam & Dubai";
  document.getElementById("anPlatform").value = "LinkedIn";
  document.getElementById("anUrl").value =
    "https://www.linkedin.com/posts/faisal-alharthi-ops_energyaudit-bms-esg-ksa-uae-activity-" +
    Math.floor(Math.random() * 90000);
  document.getElementById("anSnippet").value =
    "We are looking for a specialized engineering consultancy to conduct an ASHRAE Level 2 Energy Audit, upgrade our legacy Honeywell BMS to a central CMS/EMS platform, and prepare our 2026 GRI/Tadawul ESG Sustainability Report for our facilities in Dammam (KSA) and Jebel Ali (Dubai). Qualified consultants please reach out to Eng. Faisal Al-Harthi (Director of Plant Engineering, Arabian Gulf Logistics) at f.alharthi@agl-industrial.sa or WhatsApp +966 54 781 3390.";
}

async function runCustomAnalysis() {
  const title = document.getElementById("anTitle").value.trim();
  const snippet = document.getElementById("anSnippet").value.trim();
  const url = document.getElementById("anUrl").value.trim();
  const source_platform = document.getElementById("anPlatform").value;
  const save_to_db = document.getElementById("anSaveDb").checked;
  const send_notifications = document.getElementById("anSendNotify").checked;

  if (!snippet && !title) {
    showToast("Please paste an enquiry or post content first.", true);
    return;
  }

  const box = document.getElementById("analyzerResultBox");
  box.classList.remove("hidden");
  box.innerHTML = `<p>⏳ Analyzing enquiry &amp; checking database for duplicates...</p>`;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        snippet,
        url,
        source_platform,
        save_to_db,
        send_notifications,
      }),
    });
    const data = await res.json();
    if (!data.ok) {
      box.innerHTML = `<p style="color:#f43f5e;">${escapeHtml(data.error)}</p>`;
      return;
    }

    const lead = data.lead;
    const dupBanner = data.is_duplicate
      ? `<div class="toast error" style="margin-bottom:12px;">🚫 <strong>Duplicate / Similar Enquiry Blocked:</strong> ${escapeHtml(data.duplicate_reason)} (Not re-inserted into database)</div>`
      : data.saved_lead_id
      ? `<div class="toast" style="margin-bottom:12px;">✅ <strong>Unique Enquiry Verified:</strong> Saved to Database as Lead #${data.saved_lead_id}</div>`
      : "";

    box.innerHTML = `
      ${dupBanner}
      <div class="lead-card">
        <div class="badge-row" style="margin-bottom:10px;">
          <span class="badge badge-cat">${escapeHtml((lead.matched_services || [lead.category]).join(", "))}</span>
          <span class="badge badge-region">🌍 ${escapeHtml(lead.region)}</span>
          <span class="badge badge-score-high">🎯 AI Relevance Score: ${lead.relevance_score}/100 (${escapeHtml(lead.urgency)})</span>
          <span class="badge badge-platform">${lead.is_genuine_enquiry ? "✅ Genuine Enquiry" : "⚠️ Low Commercial Intent"}</span>
        </div>
        <div class="lead-summary"><strong>AI Summary:</strong> ${escapeHtml(lead.ai_summary)}</div>
        <div class="lead-grid-boxes">
          <div class="poc-box">
            <div class="poc-box-title">👤 Extracted Point of Contact (POC)</div>
            <div class="poc-grid">
              <div class="poc-item"><strong>Name:</strong> ${escapeHtml(lead.poc_name || "—")}</div>
              <div class="poc-item"><strong>Role:</strong> ${escapeHtml(lead.poc_role || "—")}</div>
              <div class="poc-item"><strong>Company:</strong> ${escapeHtml(lead.poc_company || "—")}</div>
              <div class="poc-item"><strong>Location:</strong> ${escapeHtml(lead.poc_location || lead.region)}</div>
              <div class="poc-item"><strong>Email:</strong> ${escapeHtml(lead.poc_email || "—")}</div>
              <div class="poc-item"><strong>Phone/WA:</strong> ${escapeHtml(lead.poc_phone || "—")}</div>
            </div>
          </div>
          <div class="pitch-box">
            <div class="pitch-box-title">💬 Suggested SETS Sales Pitch</div>
            <div>${escapeHtml(lead.suggested_pitch)}</div>
          </div>
        </div>
      </div>
    `;
    loadOverview();
  } catch (err) {
    box.innerHTML = `<p style="color:#f43f5e;">Error: ${escapeHtml(err.message)}</p>`;
  }
}

// ============================================================================
// TAB 6: SETTINGS (POSTGRESQL, LINKEDIN SERVER, OPEN-SOURCE WHATSAPP, EMAIL, AI)
// ============================================================================

function toggleWaProviderFields() {
  const provider = document.getElementById("setWaProvider").value;
  document.getElementById("waFieldsOpensource").classList.toggle("hidden", provider !== "opensource_bridge");
  document.getElementById("waFieldsWaha").classList.toggle("hidden", provider !== "waha");
  document.getElementById("waFieldsCallmebot").classList.toggle("hidden", provider !== "callmebot");
  document.getElementById("waFieldsMeta").classList.toggle("hidden", provider !== "meta_cloud");
  document.getElementById("waFieldsTwilio").classList.toggle("hidden", provider !== "twilio");
  document.getElementById("waFieldsWebhook").classList.toggle("hidden", provider !== "webhook");
}

async function loadSettingsForm() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    const s = data.settings || {};
    const db = data.db_status || {};

    document.getElementById("pgStatusBox").innerHTML = `
      <strong>Database Status:</strong> ${escapeHtml(db.engine || "PostgreSQL")}
      <div style="font-size:12px; color:#94a3b8; margin-top:2px;">${escapeHtml(db.message || "")}</div>
    `;

    document.getElementById("setPgUrl").value = s.postgres_url || "";
    document.getElementById("setPgHost").value = s.postgres_host || "localhost";
    document.getElementById("setPgPort").value = s.postgres_port || 5432;
    document.getElementById("setPgDb").value = s.postgres_db || "sets_watcher";
    document.getElementById("setPgUser").value = s.postgres_user || "postgres";
    document.getElementById("setPgPass").value = s.postgres_password || "";

    document.getElementById("setWatcherEnabled").checked = Boolean(s.watcher_enabled);
    document.getElementById("setScanInterval").value = s.scan_interval_minutes || 30;
    document.getElementById("setDedupThreshold").value = s.dedup_similarity_threshold || 0.62;
    document.getElementById("setMinScore").value = s.min_relevance_score || 55;
    document.getElementById("setAutoNotifyScore").value = s.auto_notify_min_score || 65;

    const activeRegs = s.active_regions || ["UAE", "KSA", "India"];
    document.querySelectorAll(".reg-chk").forEach((chk) => {
      chk.checked = activeRegs.includes(chk.value);
    });

    document.getElementById("setLinkedinCookie").value = s.linkedin_li_at_cookie || "";
    document.getElementById("setGeminiKey").value = s.gemini_api_key || "";
    document.getElementById("setCustomKeywords").value = s.custom_keywords || "";

    document.getElementById("setEmailEnabled").checked = Boolean(s.email_enabled);
    document.getElementById("setSmtpHost").value = s.smtp_host || "smtp.gmail.com";
    document.getElementById("setSmtpPort").value = s.smtp_port || 587;
    document.getElementById("setSmtpUser").value = s.smtp_username || "";
    document.getElementById("setSmtpPass").value = s.smtp_password || "";
    document.getElementById("setEmailFrom").value = s.email_from || "";
    document.getElementById("setEmailTo").value = s.email_to || "";

    document.getElementById("setWhatsappEnabled").checked = Boolean(s.whatsapp_enabled);
    document.getElementById("setWaProvider").value = s.whatsapp_provider || "opensource_bridge";
    document.getElementById("setWaRecipient").value = s.whatsapp_recipient_phone || "+918138858961";
    document.getElementById("setOsBridgeUrl").value =
      s.opensource_bridge_url || "http://127.0.0.1:3001/send";
    document.getElementById("setWahaUrl").value =
      s.waha_api_url || "http://127.0.0.1:3000/api/sendText";
    document.getElementById("setWahaSession").value = s.waha_session || "default";
    document.getElementById("setCallmebotKey").value = s.callmebot_api_key || "";
    document.getElementById("setMetaPhoneId").value = s.meta_phone_number_id || "";
    document.getElementById("setMetaToken").value = s.meta_access_token || "";
    document.getElementById("setTwilioSid").value = s.twilio_account_sid || "";
    document.getElementById("setTwilioToken").value = s.twilio_auth_token || "";
    document.getElementById("setTwilioFrom").value =
      s.twilio_from_number || "whatsapp:+14155238886";
    document.getElementById("setWaWebhook").value = s.whatsapp_webhook_url || "";

    toggleWaProviderFields();
  } catch (err) {
    console.error("Failed loading settings:", err);
  }
}

async function testPostgresConnectionUI() {
  const payload = {
    postgres_url: document.getElementById("setPgUrl").value.trim(),
    postgres_host: document.getElementById("setPgHost").value.trim(),
    postgres_port: parseInt(document.getElementById("setPgPort").value, 10) || 5432,
    postgres_db: document.getElementById("setPgDb").value.trim(),
    postgres_user: document.getElementById("setPgUser").value.trim(),
    postgres_password: document.getElementById("setPgPass").value,
  };
  try {
    const res = await fetch("/api/postgres/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    showToast(data.message, !data.ok);
    loadSettingsForm();
  } catch (err) {
    showToast("PostgreSQL test failed: " + err.message, true);
  }
}

function collectSettingsFromForm() {
  const active_regions = [];
  document.querySelectorAll(".reg-chk").forEach((chk) => {
    if (chk.checked) active_regions.push(chk.value);
  });

  return {
    postgres_url: document.getElementById("setPgUrl").value.trim(),
    postgres_host: document.getElementById("setPgHost").value.trim(),
    postgres_port: parseInt(document.getElementById("setPgPort").value, 10) || 5432,
    postgres_db: document.getElementById("setPgDb").value.trim(),
    postgres_user: document.getElementById("setPgUser").value.trim(),
    postgres_password: document.getElementById("setPgPass").value,

    watcher_enabled: document.getElementById("setWatcherEnabled").checked,
    scan_interval_minutes: parseInt(document.getElementById("setScanInterval").value, 10) || 30,
    dedup_similarity_threshold:
      parseFloat(document.getElementById("setDedupThreshold").value) || 0.62,
    min_relevance_score: parseInt(document.getElementById("setMinScore").value, 10) || 55,
    auto_notify_min_score: parseInt(document.getElementById("setAutoNotifyScore").value, 10) || 65,
    active_regions: active_regions.length ? active_regions : ["UAE", "KSA", "India"],
    linkedin_li_at_cookie: document.getElementById("setLinkedinCookie").value.trim(),
    gemini_api_key: document.getElementById("setGeminiKey").value.trim(),
    custom_keywords: document.getElementById("setCustomKeywords").value.trim(),

    email_enabled: document.getElementById("setEmailEnabled").checked,
    smtp_host: document.getElementById("setSmtpHost").value.trim(),
    smtp_port: parseInt(document.getElementById("setSmtpPort").value, 10) || 587,
    smtp_username: document.getElementById("setSmtpUser").value.trim(),
    smtp_password: document.getElementById("setSmtpPass").value,
    email_from: document.getElementById("setEmailFrom").value.trim(),
    email_to: document.getElementById("setEmailTo").value.trim(),

    whatsapp_enabled: document.getElementById("setWhatsappEnabled").checked,
    whatsapp_provider: document.getElementById("setWaProvider").value,
    whatsapp_recipient_phone:
      document.getElementById("setWaRecipient").value.trim() || "+918138858961",
    opensource_bridge_url: document.getElementById("setOsBridgeUrl").value.trim(),
    waha_api_url: document.getElementById("setWahaUrl").value.trim(),
    waha_session: document.getElementById("setWahaSession").value.trim(),
    callmebot_api_key: document.getElementById("setCallmebotKey").value.trim(),
    meta_phone_number_id: document.getElementById("setMetaPhoneId").value.trim(),
    meta_access_token: document.getElementById("setMetaToken").value.trim(),
    twilio_account_sid: document.getElementById("setTwilioSid").value.trim(),
    twilio_auth_token: document.getElementById("setTwilioToken").value.trim(),
    twilio_from_number: document.getElementById("setTwilioFrom").value.trim(),
    whatsapp_webhook_url: document.getElementById("setWaWebhook").value.trim(),
  };
}

async function saveAllSettings() {
  const payload = collectSettingsFromForm();
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      showToast("All PostgreSQL, LinkedIn, WhatsApp, Email, and Watcher settings saved!");
      loadOverview();
      loadSettingsForm();
    }
  } catch (err) {
    showToast("Failed to save settings: " + err.message, true);
  }
}

async function testNotificationChannel(channel) {
  const currentSettings = collectSettingsFromForm();
  try {
    const res = await fetch("/api/test-notification", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, settings: currentSettings }),
    });
    const data = await res.json();
    showToast(data.detail || "Test completed", !data.ok);
  } catch (err) {
    showToast("Test failed: " + err.message, true);
  }
}

async function loadLogs() {
  try {
    const res = await fetch("/api/logs");
    const data = await res.json();
    const scans = data.scans || [];
    const notifications = data.notifications || [];

    const scanContainer = document.getElementById("scanLogsContainer");
    if (!scans.length) {
      scanContainer.innerHTML = `<p class="muted-text">No scans recorded yet.</p>`;
    } else {
      scanContainer.innerHTML = `
        <table class="logs-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Trigger</th>
              <th>Status</th>
              <th>Found</th>
              <th>Duplicates Blocked</th>
              <th>New Leads</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            ${scans
              .map(
                (s) => `
              <tr>
                <td>#${s.id}</td>
                <td>${escapeHtml(s.trigger_type)}</td>
                <td>${escapeHtml(s.status)}</td>
                <td>${s.raw_items_found}</td>
                <td><span class="badge badge-score-med">${s.duplicates_skipped || 0} blocked</span></td>
                <td><strong>${s.new_leads_saved}</strong></td>
                <td>${escapeHtml(s.started_at)}</td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      `;
    }

    const notifyContainer = document.getElementById("notifyLogsContainer");
    if (!notifications.length) {
      notifyContainer.innerHTML = `<p class="muted-text">No notifications logged yet.</p>`;
    } else {
      notifyContainer.innerHTML = `
        <table class="logs-table">
          <thead>
            <tr>
              <th>Channel</th>
              <th>Recipient</th>
              <th>Status</th>
              <th>Preview / Error</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            ${notifications
              .map(
                (n) => `
              <tr>
                <td><strong>${escapeHtml(n.channel.toUpperCase())}</strong></td>
                <td>${escapeHtml(n.recipient)}</td>
                <td>${escapeHtml(n.status)}</td>
                <td>${escapeHtml(n.error_detail || n.message_preview)}</td>
                <td>${escapeHtml(n.created_at)}</td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      `;
    }
  } catch (err) {
    console.error("Failed loading logs:", err);
  }
}

// Initial boot & live status polling
window.addEventListener("DOMContentLoaded", () => {
  loadOverview();
  loadLeads();
  setInterval(() => {
    loadOverview();
  }, 5000);
});
