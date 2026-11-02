"""Post-save integrations: monday.com sync, then team notifications.

Runs after the webhook has already answered, so a slow or failing CRM can never lose or
delay a lead (the lead is stored first, like the n8n workflow's 'respond immediately'
webhook). Every failure is recorded on the lead and reported to the admin with manual
steps; POST /api/leads/{id}/resync retries safely.
"""
import logging

from app import monday, notifications
from app.services import get_lead, log_event, update_lead

log = logging.getLogger("lead_agent.pipeline")


def run_integrations(lead_id: int, duplicate: bool = False, notify: bool = True) -> dict:
    """Sync one stored lead to monday.com and (optionally) notify the team. Never raises."""
    result = {"crm_status": "not_configured", "crm_error": None, "email_sent": False, "slack_sent": False}
    lead = None
    try:
        lead = get_lead(lead_id)
        if lead is None:
            log.error("run_integrations: lead %s not found", lead_id)
            return result

        crm_url = ""
        if monday.configured():
            try:
                crm_url = _sync_crm(lead, duplicate)
                result["crm_status"] = "synced"
                update_lead(lead_id, crm_sync_status="synced", crm_error=None)
            except monday.MondayError as exc:
                result["crm_status"] = "failed"
                result["crm_error"] = str(exc)
                update_lead(lead_id, crm_sync_status="failed", crm_error=str(exc)[:500])
                notifications.alert_admin(*notifications.failure_report(exc.step, exc.detail, get_lead(lead_id), lead_id))
        else:
            update_lead(lead_id, crm_sync_status="not_configured")

        if notify:
            lead = get_lead(lead_id)  # fresh row: now carries crm_item_id
            sent = notifications.notify_team(lead, duplicate, crm_url)
            result["email_sent"], result["slack_sent"] = sent["email_sent"], sent["slack_sent"]
            attempted = (sent["email_configured"] and not sent["email_sent"]) or (sent["slack_configured"] and not sent["slack_sent"])
            if attempted:
                notifications.alert_admin(*notifications.failure_report(
                    "Notify sales team", "The team notification could not be delivered. The lead and task already "
                    "exist, so do not retry; tell the sales rep yourself.", lead, lead_id))
            elif not (sent["email_configured"] or sent["slack_configured"]):
                log.warning("Lead %s stored but no team notification channel is configured (SMTP or Slack).", lead_id)
        log_event(lead_id, "integrations_finished", result)
    except Exception as exc:  # last line of defence for a background task: report instead of vanishing
        log.exception("Unexpected failure while processing lead %s", lead_id)
        result["crm_status"] = result["crm_status"] if result["crm_status"] == "synced" else "failed"
        result["crm_error"] = f"{exc.__class__.__name__}: {exc}"
        try:
            notifications.alert_admin(*notifications.failure_report("Unexpected error", result["crm_error"], lead, lead_id))
        except Exception:
            log.exception("Could not send the admin alert for lead %s", lead_id)
    return result


def _sync_crm(lead: dict, duplicate: bool) -> str:
    """Create or update the monday.com item, add the note and task. Safe to re-run: finished steps are skipped."""
    lead_id = lead["id"]
    item_id = lead.get("crm_item_id") or monday.find_item(lead)
    if item_id:
        monday.update_item(item_id, lead)
    else:
        item_id = monday.create_item(lead)
    update_lead(lead_id, crm_item_id=item_id)  # persist immediately so a retry never creates a second item

    if not lead.get("crm_note_id"):
        update_lead(lead_id, crm_note_id=monday.add_note(item_id, lead, duplicate))
    if monday.tasks_configured() and not lead.get("crm_task_id"):
        update_lead(lead_id, crm_task_id=monday.create_task(lead, item_id))
    return monday.lead_url(item_id)


def report_rejected(normalized: dict) -> None:
    """Admin alert for an enquiry with no usable contact details. Never raises."""
    try:
        notifications.alert_admin(*notifications.rejected_report(normalized))
    except Exception:
        log.exception("Could not send the rejected-enquiry alert")
