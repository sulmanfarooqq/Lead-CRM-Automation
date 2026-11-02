import json

import pytest

from app import monday
from tests.conftest import API, HEADERS, lead_payload


def post(client, payload=None):
    return client.post("/webhooks/leads", json=payload or lead_payload(), headers=HEADERS)


def stored(client, lead_id):
    return client.get(f"/api/leads/{lead_id}", headers=API).json()


def test_new_lead_creates_item_note_and_task(client, fake_monday):
    r = post(client)
    assert r.json()["crm_status"] == "queued"
    lead = stored(client, r.json()["lead_id"])
    assert lead["crm_sync_status"] == "synced" and lead["crm_item_id"] and lead["crm_task_id"] and lead["crm_note_id"]
    assert [op for op, _, _ in fake_monday.calls] == [
        "items_page_by_column_values",  # looked for the email first
        "items_page_by_column_values",  # then the phone
        "create_item", "create_update", "create_item",
    ]


def test_item_columns_match_the_workflow(client, fake_monday):
    post(client)
    item = next(iter(i for i in fake_monday.items.values() if i["board"] == "111"))
    cv = item["cv"]
    assert item["name"] == "Ahmed Khan"
    assert cv["email_col"] == {"email": "ahmed.khan@example.com", "text": "ahmed.khan@example.com"}
    assert cv["phone_col"] == "+923001234567"
    assert cv["budget_col"] == "15000000"  # a number, not the text "PKR 1.5 crore": Numbers columns reject text
    assert cv["prio_col"] == {"label": "Urgent"} and cv["stage_col"] == {"label": "New"}
    assert cv["msg_col"] == {"text": "Please arrange a viewing."}
    assert len(cv["due_col"]["date"]) == 10


def test_follow_up_task_goes_to_the_tasks_board_with_a_link(client, fake_monday):
    post(client)
    task = next(i for i in fake_monday.items.values() if i["board"] == "222")
    assert task["name"] == "Follow up (Urgent): Ahmed Khan"
    assert "https://acme.monday.com/boards/111/pulses/" in task["cv"]["task_notes"]
    assert "task_due" in task["cv"]


def test_activity_note_is_html_escaped(client, fake_monday):
    post(client, lead_payload(message="<script>alert(1)</script>"))
    body = fake_monday.notes[0]["body"]
    assert "<script>" not in body and "&lt;script&gt;" in body


def test_repeat_enquiry_updates_the_existing_item_and_never_resets_stage(client, fake_monday):
    post(client)
    post(client, lead_payload(buying_timeline="6 months", message="Changed my mind"))
    assert fake_monday.count("create_item") == 3  # 1 lead item + 2 task items; no second lead item
    lead_items = [i for i in fake_monday.items.values() if i["board"] == "111"]
    assert len(lead_items) == 1
    update_vars = next(v for op, v, _ in fake_monday.calls if op == "change_multiple_column_values")
    assert "stage_col" not in json.loads(update_vars["cv"])
    assert fake_monday.count("create_update") == 2  # one note per enquiry


def test_existing_crm_item_is_found_by_phone_when_local_db_is_empty(client, fake_monday):
    """Local DB lost (e.g. ephemeral disk) but the lead exists in monday.com: no duplicate item."""
    fake_monday.items["900"] = {"name": "Old", "board": "111", "cv": {"phone_col": "+923001234567"}}
    post(client)
    assert fake_monday.count("create_item") == 1  # only the follow-up task
    assert stored(client, 1)["crm_item_id"] == "900"


def test_transient_server_errors_are_retried_three_times(client, fake_monday, admin_alerts):
    fake_monday.failures["create_item"] = [500, 502]  # two failures, then success
    r = post(client)
    assert stored(client, r.json()["lead_id"])["crm_sync_status"] == "synced"
    assert admin_alerts == []


def test_persistent_outage_is_recorded_and_alerts_the_admin(client, fake_monday, admin_alerts):
    fake_monday.failures["create_item"] = [500] * 9
    r = post(client)
    assert r.status_code == 200  # the lead is never lost because the CRM is down
    lead = stored(client, r.json()["lead_id"])
    assert lead["crm_sync_status"] == "failed" and "Create New Lead" in lead["crm_error"]
    assert fake_monday.count("create_item") == 3  # exactly MAX_TRIES attempts
    assert any(s.startswith("[FAILED]") and "Create New Lead" in s for s, _ in admin_alerts)
    assert f"/api/leads/{lead['id']}/resync" in admin_alerts[0][1]


def test_graphql_validation_error_is_not_retried(client, fake_monday, admin_alerts):
    fake_monday.failures["create_item"] = [{"errors": [{"message": "Column not found"}]}]
    post(client)
    assert fake_monday.count("create_item") == 1
    assert admin_alerts and "Column not found" in admin_alerts[0][1]


def test_resync_after_an_outage_creates_exactly_one_item(client, fake_monday, admin_alerts):
    fake_monday.failures["create_item"] = [500] * 3
    lead_id = post(client).json()["lead_id"]
    assert stored(client, lead_id)["crm_sync_status"] == "failed"
    assert client.post(f"/api/leads/{lead_id}/resync", headers=API).json()["status"] == "resync queued"
    lead = stored(client, lead_id)
    assert lead["crm_sync_status"] == "synced" and lead["crm_error"] is None
    assert len([i for i in fake_monday.items.values() if i["board"] == "111"]) == 1


def test_resync_after_a_partial_failure_does_not_duplicate_finished_steps(client, fake_monday, admin_alerts):
    fake_monday.failures["create_update"] = [500] * 3  # item is created, the note fails
    lead_id = post(client).json()["lead_id"]
    lead = stored(client, lead_id)
    assert lead["crm_sync_status"] == "failed" and lead["crm_item_id"] and not lead["crm_note_id"]
    client.post(f"/api/leads/{lead_id}/resync", headers=API)
    assert len([i for i in fake_monday.items.values() if i["board"] == "111"]) == 1
    assert stored(client, lead_id)["crm_note_id"]


def test_failed_leads_can_be_listed(client, fake_monday, admin_alerts):
    fake_monday.failures["create_item"] = [500] * 3
    post(client)
    assert len(client.get("/api/leads?crm_status=failed", headers=API).json()) == 1
    assert client.get("/api/leads?crm_status=synced", headers=API).json() == []


def test_not_configured_is_reported_not_treated_as_an_error(client):
    r = post(client)
    assert r.json()["crm_status"] == "not_configured"
    assert stored(client, r.json()["lead_id"])["crm_sync_status"] == "not_configured"


def test_task_board_is_optional(client, fake_monday, set_env):
    set_env(MONDAY_TASK_BOARD_ID="")
    post(client)
    assert all(i["board"] == "111" for i in fake_monday.items.values())


def test_api_token_is_sent_but_never_logged(client, fake_monday, caplog):
    fake_monday.failures["create_item"] = [500] * 3
    with caplog.at_level("DEBUG"):
        post(client)
    assert fake_monday.calls[0][2]["Authorization"] == "tok_test"
    assert "tok_test" not in caplog.text


def test_api_version_header_is_only_sent_when_configured(client, fake_monday, set_env):
    post(client)
    assert "API-Version" not in fake_monday.calls[0][2]
    set_env(MONDAY_API_VERSION="2026-01")
    post(client, lead_payload(email="b@example.com", phone="03111234567"))
    assert fake_monday.calls[-1][2]["API-Version"] == "2026-01"
