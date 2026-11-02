"""monday.com GraphQL client.

Mirrors the HTTP nodes of the n8n workflow: look the lead up by email (then phone), update
it if found or create it if not, add an activity note, and create a follow-up task on a
tasks board. Requests are retried up to 3 times with a 2 second wait, like the workflow.
"""
import html
import json
import logging
import time

import httpx

from app.config import get_settings
from app.services import rep_monday_user_id

log = logging.getLogger("lead_agent.monday")

MAX_TRIES = 3
RETRY_WAIT_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 20

LOOKUP_QUERY = (
    "query ($boardId: ID!, $col: String!, $val: String!) { items_page_by_column_values("
    "board_id: $boardId, limit: 1, columns: [{column_id: $col, column_values: [$val]}]) { items { id name } } }"
)
CREATE_QUERY = (
    "mutation ($boardId: ID!, $groupId: String, $name: String!, $cv: JSON!) { create_item("
    "board_id: $boardId, group_id: $groupId, item_name: $name, column_values: $cv, "
    "create_labels_if_missing: true) { id } }"
)
UPDATE_QUERY = (
    "mutation ($boardId: ID!, $itemId: ID!, $cv: JSON!) { change_multiple_column_values("
    "board_id: $boardId, item_id: $itemId, column_values: $cv, create_labels_if_missing: true) { id } }"
)
NOTE_QUERY = "mutation ($itemId: ID!, $body: String!) { create_update(item_id: $itemId, body: $body) { id } }"


class MondayError(RuntimeError):
    """A monday.com call failed after retries. `step` names the failed stage for the admin alert."""

    def __init__(self, step: str, message: str):
        super().__init__(f"{step}: {message}")
        self.step = step
        self.detail = message


# Thin indirections so tests can replace the network and the clock.
def _http_post(*args, **kwargs):
    return httpx.post(*args, **kwargs)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def configured() -> bool:
    s = get_settings()
    return bool(s.monday_api_token and s.monday_board_id)


def _retriable_graphql_error(errors) -> bool:
    text = json.dumps(errors).lower()
    return any(word in text for word in ("rate_limit", "ratelimit", "complexity", "temporarily", "timeout"))


def _request(step: str, query: str, variables: dict) -> dict:
    s = get_settings()
    headers = {"Authorization": s.monday_api_token, "Content-Type": "application/json"}
    if s.monday_api_version:
        headers["API-Version"] = s.monday_api_version
    last = "unknown error"
    for attempt in range(1, MAX_TRIES + 1):
        try:
            response = _http_post(
                s.monday_api_url, headers=headers, json={"query": query, "variables": variables},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            last = f"network error ({exc.__class__.__name__})"
        else:
            if response.status_code == 429 or response.status_code >= 500:
                last = f"HTTP {response.status_code}"
            elif response.status_code >= 400:
                raise MondayError(step, f"HTTP {response.status_code}: {response.text[:300]}")
            else:
                try:
                    body = response.json()
                except ValueError:
                    raise MondayError(step, "monday.com returned a response that is not JSON") from None
                errors = body.get("errors") or body.get("error_message")
                if errors:
                    last = json.dumps(errors)[:400]
                    if not _retriable_graphql_error(errors):
                        raise MondayError(step, last)
                elif not body.get("data"):
                    raise MondayError(step, "monday.com returned no data")
                else:
                    return body["data"]
        if attempt < MAX_TRIES:
            log.warning("monday.com %s failed (attempt %d/%d): %s", step, attempt, MAX_TRIES, last)
            _sleep(RETRY_WAIT_SECONDS)
    raise MondayError(step, f"{last} (after {MAX_TRIES} attempts)")


def lead_url(item_id: str) -> str:
    s = get_settings()
    base = s.monday_account_url.rstrip("/")
    return f"{base}/boards/{s.monday_board_id}/pulses/{item_id}" if base else ""


def column_values(lead: dict, *, creating: bool) -> dict:
    """Column payload. Only columns that have both a configured ID and a value are sent."""
    s = get_settings()
    cv: dict = {}

    def put(column_id: str, value) -> None:
        if column_id and value not in (None, ""):
            cv[column_id] = value

    put(s.monday_email_column_id, {"email": lead["email"], "text": lead["email"]} if lead.get("email") else None)
    put(s.monday_phone_column_id, lead.get("phone"))
    put(s.monday_property_type_column_id, lead.get("property_type"))
    put(s.monday_budget_column_id, str(lead["budget_value"]) if lead.get("budget_value") else None)
    put(s.monday_location_column_id, lead.get("preferred_location"))
    put(s.monday_timeline_column_id, lead.get("buying_timeline"))
    put(s.monday_message_column_id, {"text": lead["message"]} if lead.get("message") else None)
    put(s.monday_priority_column_id, {"label": lead["priority"]})
    put(s.monday_followup_column_id, {"date": (lead.get("follow_up_due") or "")[:10]})
    owner_id = rep_monday_user_id(lead.get("assigned_to"))
    if owner_id.isdigit():
        put(s.monday_owner_column_id, {"personsAndTeams": [{"id": int(owner_id), "kind": "person"}]})
    if creating:
        put(s.monday_stage_column_id, {"label": "New"})  # stage is only set on creation, never overwritten
    return cv


def find_item(lead: dict) -> str | None:
    """Return an existing item's id, searching by email first and then by phone."""
    s = get_settings()
    probes = ((s.monday_email_column_id, lead.get("email")), (s.monday_phone_column_id, lead.get("phone")))
    for column_id, value in probes:
        if not column_id or not value:
            continue
        data = _request(
            "Find Existing Lead", LOOKUP_QUERY,
            {"boardId": str(s.monday_board_id), "col": column_id, "val": value},
        )
        items = (data.get("items_page_by_column_values") or {}).get("items") or []
        if items:
            return str(items[0]["id"])
    return None


def create_item(lead: dict) -> str:
    s = get_settings()
    data = _request(
        "Create New Lead", CREATE_QUERY,
        {"boardId": str(s.monday_board_id), "groupId": s.monday_group_id or None,
         "name": lead["full_name"], "cv": json.dumps(column_values(lead, creating=True))},
    )
    return str(data["create_item"]["id"])


def update_item(item_id: str, lead: dict) -> str:
    s = get_settings()
    data = _request(
        "Update Existing Lead", UPDATE_QUERY,
        {"boardId": str(s.monday_board_id), "itemId": str(item_id), "cv": json.dumps(column_values(lead, creating=False))},
    )
    return str(data["change_multiple_column_values"]["id"])


def add_note(item_id: str, lead: dict, duplicate: bool) -> str:
    esc = html.escape
    budget = f"{lead['budget_value']:,}" if lead.get("budget_value") else "—"
    flags = json.loads(lead.get("review_reasons") or "[]")
    body = "<br>".join([
        f"<b>{'Repeat enquiry' if duplicate else 'New enquiry'} received via {esc(lead.get('source') or 'web form')}</b>",
        f"Priority: {esc(lead['priority'])}",
        f"Follow-up: {esc(lead.get('follow_up_action') or '')} (due {(lead.get('follow_up_due') or '')[:10]})",
        f"Budget: {budget} | Timeline: {esc(lead.get('buying_timeline') or '—')} | Location: {esc(lead.get('preferred_location') or '—')}",
        f"Property type: {esc(lead.get('property_type') or '—')}",
        f"Message: {esc(lead.get('message') or '—')}",
        f"Review flags: {esc('; '.join(flags))}" if flags else "Review flags: none",
    ])
    data = _request("Log Enquiry Update", NOTE_QUERY, {"itemId": str(item_id), "body": body})
    return str(data["create_update"]["id"])


def tasks_configured() -> bool:
    return bool(get_settings().monday_task_board_id)


def create_task(lead: dict, item_id: str) -> str:
    s = get_settings()
    cv: dict = {}
    if s.monday_task_due_column_id:
        cv[s.monday_task_due_column_id] = {"date": (lead.get("follow_up_due") or "")[:10]}
    if s.monday_task_notes_column_id:
        cv[s.monday_task_notes_column_id] = f"{lead.get('follow_up_action') or ''} | Lead: {lead_url(item_id)}"
    data = _request(
        "Create Follow-up Task", CREATE_QUERY,
        {"boardId": str(s.monday_task_board_id), "groupId": s.monday_task_group_id or None,
         "name": f"Follow up ({lead['priority']}): {lead['full_name']}", "cv": json.dumps(cv)},
    )
    return str(data["create_item"]["id"])
