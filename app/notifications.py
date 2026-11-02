"""Internal notifications: email (SMTP) and Slack, plus admin alerts.

Nothing in this module ever contacts the buyer. Team emails go to the assigned sales
representative; rejected-lead and failure alerts go to ADMIN_EMAIL and/or Slack.
"""
import html
import json
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.config import get_settings

log = logging.getLogger("lead_agent.notify")
PLACEHOLDER_DOMAINS = ("@example.com", "@example.org", "@example.net")


def _http_post(*args, **kwargs):
    return httpx.post(*args, **kwargs)


def _smtp_ready() -> bool:
    s = get_settings()
    return bool(s.smtp_host and (s.smtp_from_email or s.smtp_username))


def send_email(to: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send one email. Returns True on success; failures are logged, never raised."""
    s = get_settings()
    if not (_smtp_ready() and to):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s.smtp_from_email or s.smtp_username
    msg["To"] = to
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    try:
        context = ssl.create_default_context()
        if s.smtp_port == 465:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=context)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
        with server:
            if s.smtp_port != 465 and s.smtp_use_tls:
                server.starttls(context=context)
            if s.smtp_username:
                server.login(s.smtp_username, s.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:  # smtplib raises many unrelated types; never leak credentials into the log
        log.error("SMTP send to %s failed: %s: %s", to, exc.__class__.__name__, exc)
        return False


def send_slack(text: str) -> bool:
    s = get_settings()
    if not s.slack_webhook_url:
        return False
    try:
        response = _http_post(s.slack_webhook_url, json={"text": text}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        log.error("Slack webhook failed: %s", exc.__class__.__name__)
        return False


def _slack_escape(value) -> str:
    return str(value if value is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _money(value) -> str:
    return f"{value:,}" if value else "—"


def _table(rows: list[tuple[str, str]]) -> str:
    esc = html.escape
    cells = "".join(
        f'<tr><td style="padding:6px 12px;background:#f5f5f5"><b>{esc(k)}</b></td>'
        f'<td style="padding:6px 12px">{esc(str(v))}</td></tr>'
        for k, v in rows
    )
    return f'<table style="border-collapse:collapse;width:100%">{cells}</table>'


def lead_rows(lead: dict) -> list[tuple[str, str]]:
    flags = json.loads(lead.get("review_reasons") or "[]")
    rows = [
        ("Name", lead["full_name"]),
        ("Priority", lead["priority"]),
        ("Assigned to", lead.get("assigned_to") or "Unassigned"),
        ("Follow-up action", f"{lead.get('follow_up_action') or ''} (due {(lead.get('follow_up_due') or '')[:16].replace('T', ' ')})"),
        ("Email", lead.get("email") or "—"),
        ("Phone", lead.get("phone") or "—"),
        ("Property type", lead.get("property_type") or "—"),
        ("Budget", _money(lead.get("budget_value"))),
        ("Preferred location", lead.get("preferred_location") or "—"),
        ("Buying timeline", lead.get("buying_timeline") or "—"),
        ("Message", lead.get("message") or "—"),
    ]
    if flags:
        rows.append(("Review flags", "; ".join(flags)))
    return rows


def recipient_for(lead: dict) -> str:
    """The assigned rep's email, unless it is still a sample address from the template."""
    s = get_settings()
    email = (lead.get("assigned_email") or "").strip()
    if email and not email.lower().endswith(PLACEHOLDER_DOMAINS):
        return email
    return s.sales_rep_email


def notify_team(lead: dict, duplicate: bool, crm_url: str = "") -> dict:
    """Email the assigned rep and post to Slack. Returns what was configured and what was delivered."""
    s = get_settings()
    subject = f"[{lead['priority'].upper()}] {'Repeat enquiry' if duplicate else 'New lead'}: {lead['full_name']}"
    rows = lead_rows(lead)
    link = f'<p><a href="{html.escape(crm_url)}" style="display:inline-block;padding:10px 18px;background:#0073ea;color:#fff;text-decoration:none;border-radius:4px">Open lead in monday.com</a></p>' if crm_url else ""
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:620px">'
        f"<h2>{'Repeat enquiry (existing lead updated)' if duplicate else 'New lead'}</h2>{_table(rows)}{link}"
        '<p style="color:#777;font-size:12px">Sent by the Real Estate Lead Response Agent. No message has been sent to the buyer.</p></div>'
    )
    text_body = "\n".join(f"{k}: {v}" for k, v in rows) + (f"\nCRM: {crm_url}" if crm_url else "") + \
        "\n\nThe buyer has not been contacted by this system."

    recipient = recipient_for(lead)
    result = {
        "email_configured": _smtp_ready() and bool(recipient),
        "slack_configured": bool(s.slack_webhook_url),
        "email_sent": False,
        "slack_sent": False,
    }
    if result["email_configured"]:
        result["email_sent"] = send_email(recipient, subject, html_body, text_body)
    if result["slack_configured"]:
        slack_text = f"*{_slack_escape(subject)}*\n" + "\n".join(f"{_slack_escape(k)}: {_slack_escape(v)}" for k, v in rows)
        if crm_url:
            slack_text += f"\n<{crm_url}|Open lead in monday.com>"
        result["slack_sent"] = send_slack(slack_text)
    return result


def alert_admin(subject: str, html_body: str, text_body: str) -> None:
    """Tell the admin something needs attention. Always logged; emailed/Slacked when configured."""
    s = get_settings()
    log.error("ADMIN ALERT: %s", subject)
    if s.admin_email:
        send_email(s.admin_email, subject, html_body, text_body)
    if s.slack_webhook_url:
        send_slack(f"*{_slack_escape(subject)}*\n{_slack_escape(text_body)[:2500]}")


def rejected_report(normalized: dict) -> tuple[str, str, str]:
    subject = f"[REJECTED ENQUIRY] {normalized['reject_reason']} - {normalized['full_name']}"
    payload = json.dumps(normalized["raw"], indent=2, default=str)
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:620px"><h2>Enquiry rejected by automation</h2>'
        f"<p><b>Reason:</b> {html.escape(normalized['reject_reason'])}</p>"
        "<p>Nothing was stored. If the buyer can be reached some other way, add them manually.</p>"
        f'<pre style="background:#f5f5f5;padding:12px;white-space:pre-wrap">{html.escape(payload)}</pre></div>'
    )
    text_body = (
        f"Enquiry rejected by automation.\nReason: {normalized['reject_reason']}\n"
        f"Nothing was stored. If the buyer can be reached some other way, add them manually.\n\n{payload}"
    )
    return subject, html_body, text_body


def failure_report(step: str, error: str, lead: dict | None, lead_id: int | None) -> tuple[str, str, str]:
    subject = f"[FAILED] Lead automation error at: {step}"
    rows = [("Step", step), ("Error", error), ("Lead ID", lead_id if lead_id is not None else "—")]
    if lead:
        rows += [(k, v) for k, v in lead_rows(lead)]
    steps = [
        "Search the leads board in monday.com for the buyer's email or phone.",
        "If it exists, update the fields above and set the priority. If not, create the item with stage \"New\".",
        "Add a follow-up task using the priority rules (Urgent: call within 1 hour; High: 24 hours; Nurture: 3 days; Needs review: verify details).",
        "Contact the buyer yourself. The automation never emails buyers.",
    ]
    retry = (
        f"Retry safely: POST /api/leads/{lead_id}/resync (header X-API-Key). The duplicate check means a retry updates "
        "the existing monday.com item instead of creating a second one."
        if lead_id is not None else "No lead was stored, so there is nothing to retry."
    )
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:640px"><h2 style="color:#c62828">Lead automation failed</h2>'
        f"{_table(rows)}<h3>Process it manually</h3><ol>{''.join(f'<li>{html.escape(x)}</li>' for x in steps)}</ol>"
        f"<h3>Retry</h3><p>{html.escape(retry)}</p></div>"
    )
    text_body = "\n".join(f"{k}: {v}" for k, v in rows) + "\n\nProcess it manually:\n" + \
        "\n".join(f"{i}. {x}" for i, x in enumerate(steps, 1)) + f"\n\n{retry}"
    return subject, html_body, text_body
