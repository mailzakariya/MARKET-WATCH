"""
Multi-Channel Team Notification Engine for SETS (www.sets4us.com).
Supports:
1. Open-Source Free WhatsApp APIs:
   - SETS Local Open-Source Baileys Bridge (http://127.0.0.1:3001/send) with user-configured recipient dispatch
   - WAHA (Open-Source WhatsApp HTTP API - http://127.0.0.1:3000/api/sendText)
   - CallMeBot Free WhatsApp API
   - Meta WhatsApp Cloud API / Twilio / Custom Webhook
2. Email Alerts via SMTP (Gmail, Office365, Zoho, or custom SMTP)
3. Multi-recipient routing from the Team Contacts configuration table (Add/Edit/Delete numbers & emails)
"""

import base64
import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

from watcher.database import list_team_contacts, log_notification, mark_lead_notified


def get_active_whatsapp_recipients(
    settings: Dict[str, Any], lead_region: str = "ALL"
) -> List[str]:
    contacts = list_team_contacts(active_only=True)
    phones: List[str] = []

    for c in contacts:
        if not c.get("notify_whatsapp") or not c.get("phone"):
            continue
        r_filter = (c.get("region_filter") or "ALL").upper()
        if r_filter in ("ALL", lead_region.upper()):
            p = c["phone"].strip()
            if p and p not in phones:
                phones.append(p)

    # Also include primary fallback number from settings if not already in list
    primary = (settings.get("whatsapp_recipient_phone") or "").strip()
    if primary and primary not in phones:
        phones.append(primary)

    return phones


def get_active_email_recipients(
    settings: Dict[str, Any], lead_region: str = "ALL"
) -> List[str]:
    contacts = list_team_contacts(active_only=True)
    emails: List[str] = []

    for c in contacts:
        if not c.get("notify_email") or not c.get("email"):
            continue
        r_filter = (c.get("region_filter") or "ALL").upper()
        if r_filter in ("ALL", lead_region.upper()):
            em = c["email"].strip()
            if em and em not in emails:
                emails.append(em)

    raw_setting_emails = (settings.get("email_to") or "").strip()
    for e in raw_setting_emails.split(","):
        em = e.strip()
        if em and em not in emails:
            emails.append(em)

    return emails


def format_whatsapp_message(lead: Dict[str, Any]) -> str:
    services = lead.get("matched_services") or [lead.get("category", "Energy Audit")]
    services_str = ", ".join(services) if isinstance(services, list) else str(services)

    poc_lines = []
    if lead.get("poc_name"):
        poc_lines.append(f"• *Name:* {lead['poc_name']}")
    if lead.get("poc_role") or lead.get("poc_company"):
        role_comp = " - ".join([x for x in [lead.get("poc_role"), lead.get("poc_company")] if x])
        poc_lines.append(f"• *Org/Role:* {role_comp}")
    if lead.get("poc_email"):
        poc_lines.append(f"• *Email:* {lead['poc_email']}")
    if lead.get("poc_phone"):
        poc_lines.append(f"• *Phone/WA:* {lead['poc_phone']}")
    if lead.get("poc_linkedin"):
        poc_lines.append(f"• *LinkedIn:* {lead['poc_linkedin']}")
    if lead.get("poc_location"):
        poc_lines.append(f"• *Location:* {lead['poc_location']}")

    poc_block = "\n".join(poc_lines) if poc_lines else "• See source link for contact details"

    msg = (
        f"🚨 *SETS AI Lead Watcher Alert*\n"
        f"🌐 *www.sets4us.com*\n\n"
        f"📌 *Enquiry:* {lead.get('title', 'New Opportunity')}\n"
        f"🏷️ *Services:* {services_str}\n"
        f"🌍 *Region:* {lead.get('region', 'UAE')} | *Platform:* {lead.get('source_platform', 'Web')}\n"
        f"🎯 *AI Score:* {lead.get('relevance_score', 75)}/100 ({lead.get('urgency', 'High')} Priority)\n\n"
        f"📝 *AI Summary:*\n{lead.get('ai_summary', '')}\n\n"
        f"👤 *Point of Contact (POC):*\n{poc_block}\n\n"
        f"🔗 *Source URL:*\n{lead.get('url', '')}"
    )
    return msg


def format_email_html(lead: Dict[str, Any]) -> Tuple[str, str]:
    services = lead.get("matched_services") or [lead.get("category", "Energy Audit")]
    services_str = ", ".join(services) if isinstance(services, list) else str(services)

    subject = (
        f"[SETS Lead Alert - {lead.get('region', 'UAE')}] "
        f"{lead.get('category', 'Energy Audit')} ({lead.get('relevance_score', 80)}% Match): "
        f"{lead.get('title', '')[:75]}"
    )

    html_body = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7fb; padding: 24px; color: #1e293b;">
      <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
        <div style="background: linear-gradient(135deg, #0f172a 0%, #047857 100%); color: #ffffff; padding: 20px 24px;">
          <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; opacity: 0.85;">SETS AI Lead Watcher • www.sets4us.com</div>
          <h2 style="margin: 8px 0 4px 0; font-size: 20px;">{lead.get('title', 'New Business Enquiry')}</h2>
          <div style="font-size: 13px; margin-top: 6px;">
            <span style="background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 99px; margin-right: 6px;">{services_str}</span>
            <span style="background: rgba(255,255,255,0.2); padding: 3px 10px; border-radius: 99px; margin-right: 6px;">Region: {lead.get('region', 'UAE')}</span>
            <span style="background: #10b981; color: #052e16; font-weight: bold; padding: 3px 10px; border-radius: 99px;">Score: {lead.get('relevance_score', 80)}/100 ({lead.get('urgency', 'High')})</span>
          </div>
        </div>
        <div style="padding: 24px;">
          <h3 style="margin-top: 0; color: #0f172a; font-size: 15px;">AI Executive Analysis</h3>
          <p style="background: #f8fafc; padding: 12px 16px; border-left: 4px solid #10b981; border-radius: 4px; margin: 8px 0 20px 0; font-size: 14px; line-height: 1.5;">
            {lead.get('ai_summary', '')}
          </p>

          <h3 style="color: #0f172a; font-size: 15px; margin-bottom: 10px;">Point of Contact (POC) Details</h3>
          <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600; width: 140px;">Contact Name:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_name') or 'Not explicitly listed'}</td></tr>
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600;">Role / Title:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_role') or '—'}</td></tr>
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600;">Organization:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_company') or '—'}</td></tr>
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600;">Email:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_email') or '—'}</td></tr>
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600;">Phone / WhatsApp:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_phone') or '—'}</td></tr>
            <tr><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9; font-weight: 600;">Location:</td><td style="padding: 6px 10px; border-bottom: 1px solid #f1f5f9;">{lead.get('poc_location') or lead.get('region', 'UAE')}</td></tr>
          </table>

          <h3 style="color: #0f172a; font-size: 15px; margin-bottom: 8px;">Original Post / Enquiry Snippet</h3>
          <div style="background: #f8fafc; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #475569; margin-bottom: 20px; line-height: 1.5;">
            {lead.get('snippet', '')}
          </div>

          <h3 style="color: #0f172a; font-size: 15px; margin-bottom: 8px;">Recommended Outreach Pitch</h3>
          <div style="background: #ecfdf5; border: 1px solid #a7f3d0; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #065f46; margin-bottom: 20px;">
            {lead.get('suggested_pitch', '')}
          </div>

          <div style="margin-top: 20px;">
            <a href="{lead.get('url', '#')}" style="display: inline-block; background: #047857; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px;">Open Original Source Post</a>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return subject, html_body


def send_email_notification(
    lead: Dict[str, Any],
    settings: Dict[str, Any],
    override_recipients: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    smtp_host = (settings.get("smtp_host") or "").strip()
    smtp_port = int(settings.get("smtp_port") or 587)
    smtp_user = (settings.get("smtp_username") or "").strip()
    smtp_pass = (settings.get("smtp_password") or "").strip()
    email_from = (settings.get("email_from") or smtp_user).strip()

    recipients = override_recipients or get_active_email_recipients(
        settings, lead.get("region", "ALL")
    )

    if not smtp_host or not recipients or not smtp_user or not smtp_pass:
        return (
            False,
            "SMTP credentials or recipient emails not configured. Add team emails in Team Contacts or SMTP Settings.",
        )

    subject, html_body = format_email_html(lead)
    plain_text = format_whatsapp_message(lead)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if settings.get("smtp_use_tls", True):
                server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(email_from, recipients, msg.as_string())
        server.quit()

        lead_id = lead.get("id")
        if lead_id:
            mark_lead_notified(int(lead_id), "email")
        log_notification(lead_id, "email", ", ".join(recipients), "sent", subject)
        return True, f"Email alert sent to {', '.join(recipients)}"
    except Exception as exc:
        log_notification(
            lead.get("id"), "email", ", ".join(recipients), "failed", subject, str(exc)
        )
        return False, f"SMTP error: {exc}"


def _send_single_whatsapp(
    recipient: str, message_text: str, settings: Dict[str, Any], lead: Dict[str, Any]
) -> Tuple[bool, str]:
    provider = (settings.get("whatsapp_provider") or "opensource_bridge").strip()
    clean_digits = "".join(ch for ch in recipient if ch.isdigit())

    try:
        if provider == "opensource_bridge":
            bridge_url = (
                settings.get("opensource_bridge_url") or "http://127.0.0.1:3001/send"
            ).strip()
            payload = {"phone": recipient, "message": message_text}
            req = urllib.request.Request(
                bridge_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if not res_data.get("ok", True):
                    return False, res_data.get("error", "Open-source bridge error")

        elif provider == "waha":
            waha_url = (
                settings.get("waha_api_url") or "http://127.0.0.1:3000/api/sendText"
            ).strip()
            session_name = (settings.get("waha_session") or "default").strip()
            api_key = (settings.get("waha_api_key") or "").strip()
            payload = {
                "chatId": f"{clean_digits}@c.us",
                "text": message_text,
                "session": session_name,
            }
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["X-Api-Key"] = api_key
            req = urllib.request.Request(
                waha_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp.read()

        elif provider == "callmebot":
            apikey = (settings.get("callmebot_api_key") or "").strip()
            if not apikey:
                return (
                    False,
                    f"CallMeBot API Key is required for {recipient}. (Or use the included Open-Source Local Bridge via start_whatsapp_bridge.bat)",
                )
            clean_phone = urllib.parse.quote_plus(recipient.replace(" ", ""))
            encoded_msg = urllib.parse.quote_plus(message_text)
            url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={apikey}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()

        elif provider == "meta_cloud":
            phone_id = (settings.get("meta_phone_number_id") or "").strip()
            token = (settings.get("meta_access_token") or "").strip()
            if not phone_id or not token:
                return False, "Meta WhatsApp Cloud API requires Phone Number ID and Access Token."
            url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_digits,
                "type": "text",
                "text": {"preview_url": True, "body": message_text},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()

        elif provider == "twilio":
            sid = (settings.get("twilio_account_sid") or "").strip()
            token = (settings.get("twilio_auth_token") or "").strip()
            from_num = (settings.get("twilio_from_number") or "whatsapp:+14155238886").strip()
            if not sid or not token:
                return False, "Twilio WhatsApp requires Account SID and Auth Token."
            to_formatted = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"
            from_formatted = from_num if from_num.startswith("whatsapp:") else f"whatsapp:{from_num}"
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
            data = urllib.parse.urlencode(
                {"From": from_formatted, "To": to_formatted, "Body": message_text}
            ).encode("utf-8")
            auth_b64 = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()

        elif provider == "webhook":
            webhook_url = (settings.get("whatsapp_webhook_url") or "").strip()
            if not webhook_url:
                return False, "Custom Webhook URL is not configured."
            payload = {"recipient": recipient, "message": message_text, "lead": lead}
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        else:
            return False, f"Unknown WhatsApp provider: {provider}"

        return True, f"Sent to {recipient}"
    except Exception as exc:
        hint = ""
        if provider == "opensource_bridge":
            hint = " (Tip: Run start_whatsapp_bridge.bat to start the free local WhatsApp server on port 3001 and scan QR with your WhatsApp phone)"
        return False, f"WhatsApp ({provider}) error for {recipient}: {exc}{hint}"


def send_whatsapp_notification(
    lead: Dict[str, Any],
    settings: Dict[str, Any],
    override_recipients: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    recipients = override_recipients or get_active_whatsapp_recipients(
        settings, lead.get("region", "ALL")
    )
    if not recipients:
        return False, "No active WhatsApp numbers configured in Team Contacts."

    message_text = format_whatsapp_message(lead)
    sent_to: List[str] = []
    errors: List[str] = []

    for phone in recipients:
        ok, detail = _send_single_whatsapp(phone, message_text, settings, lead)
        if ok:
            sent_to.append(phone)
            log_notification(lead.get("id"), "whatsapp", phone, "sent", message_text[:200])
        else:
            errors.append(detail)
            log_notification(
                lead.get("id"), "whatsapp", phone, "failed", message_text[:200], detail
            )

    if sent_to:
        lead_id = lead.get("id")
        if lead_id:
            mark_lead_notified(int(lead_id), "whatsapp")
        summary = f"WhatsApp alert sent to {', '.join(sent_to)}"
        if errors:
            summary += f" (Partial errors: {'; '.join(errors[:2])})"
        return True, summary

    return False, "; ".join(errors) if errors else "WhatsApp dispatch failed."


def notify_for_lead(
    lead: Dict[str, Any], settings: Dict[str, Any], force: bool = False
) -> Dict[str, Any]:
    """
    Dispatch Email and/or WhatsApp notifications to all active Team Contacts for a qualified lead.
    """
    results = {"email": None, "whatsapp": None, "sent_count": 0}
    min_score = int(settings.get("auto_notify_min_score", 65))
    if not force and int(lead.get("relevance_score", 0)) < min_score:
        return results

    if settings.get("email_enabled") and (force or not lead.get("notified_email")):
        ok, detail = send_email_notification(lead, settings)
        results["email"] = {"ok": ok, "detail": detail}
        if ok:
            results["sent_count"] += 1

    if settings.get("whatsapp_enabled") and (force or not lead.get("notified_whatsapp")):
        ok, detail = send_whatsapp_notification(lead, settings)
        results["whatsapp"] = {"ok": ok, "detail": detail}
        if ok:
            results["sent_count"] += 1

    return results
