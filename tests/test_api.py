import pytest
from fastapi.testclient import TestClient

from app.services import now_local
from tests.conftest import API, API_KEY, HEADERS, WEBHOOK_SECRET, lead_payload


def post(client, payload, headers=HEADERS):
    return client.post("/webhooks/leads", json=payload, headers=headers)


# ------------------------------------------------------------------ service endpoints

def test_health_and_root(client):
    assert client.get("/health").json() == {"status": "ok"}
    root = client.get("/").json()
    assert root["status"] == "running" and root["webhook"] == "/webhooks/leads"


# ------------------------------------------------------------------------ webhook auth

def test_wrong_or_missing_secret_is_rejected(client):
    assert post(client, lead_payload(), headers={"X-Webhook-Secret": "wrong"}).status_code == 401
    assert post(client, lead_payload(), headers={}).status_code == 401
    assert client.get("/api/leads", headers=API).json() == []  # nothing was stored


def test_secret_in_json_body_is_accepted(client):
    r = post(client, {**lead_payload(), "secret": WEBHOOK_SECRET}, headers={})
    assert r.status_code == 200


def test_secret_is_not_stored(client):
    r = post(client, {**lead_payload(), "secret": WEBHOOK_SECRET}, headers={})
    stored = client.get(f"/api/leads/{r.json()['lead_id']}", headers=API).json()
    assert WEBHOOK_SECRET not in str(stored)


# ------------------------------------------------------------------- lead processing

def test_new_urgent_lead(client):
    r = post(client, lead_payload())
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["priority"], body["is_duplicate"]) == ("created", "Urgent", False)
    assert body["warnings"] == [] and body["crm_status"] == "not_configured"
    assert "within 1 hour" in body["follow_up_action"]
    lead = client.get(f"/api/leads/{body['lead_id']}", headers=API).json()
    assert lead["phone"] == "+923001234567" and lead["budget_value"] == 15_000_000


def test_apps_script_camelcase_payload(client):
    r = post(client, {"fullName": "Sara Ali", "email": "sara@example.com", "phone": "03111234567",
                      "propertyType": "House", "budget": "50 lakh", "preferredLocation": "DHA",
                      "buyingTimeline": "within 2 weeks", "message": "Hello", "submittedAt": "2026-11-01T10:00:00Z"})
    assert r.status_code == 200 and r.json()["priority"] == "High priority"
    lead = client.get(f"/api/leads/{r.json()['lead_id']}", headers=API).json()
    assert (lead["full_name"], lead["property_type"], lead["preferred_location"]) == ("Sara Ali", "House", "DHA")


def test_google_form_title_case_payload(client):
    r = post(client, {"Full Name": "Title Case", "Email": "t@example.com", "Phone": "03001234567", "Budget": "3 crore",
                      "Buying Timeline": "within 7 days", "Message": "Hi"})
    assert r.status_code == 200 and r.json()["priority"] == "Urgent"


def test_numeric_phone_and_budget_are_accepted(client):
    r = post(client, lead_payload(phone=3001234567, budget=5000000))
    assert r.status_code == 200
    assert client.get(f"/api/leads/{r.json()['lead_id']}", headers=API).json()["budget_value"] == 5_000_000


@pytest.mark.parametrize("override, flag", [
    ({"email": ""}, "Missing email"),
    ({"email": "not-an-email"}, "Invalid email format"),
    ({"phone": None}, "Missing phone"),
    ({"phone": "123"}, "Invalid phone number"),
    ({"full_name": None}, "Missing name"),
    ({"budget": None}, "Missing budget"),
    ({"buying_timeline": None}, "Missing buying timeline"),
])
def test_imperfect_leads_are_kept_and_sent_to_review(client, override, flag):
    r = post(client, lead_payload(**override))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["priority"] == "Needs review" and flag in body["warnings"]


def test_lead_without_any_contact_is_rejected_and_admin_is_told(client, admin_alerts):
    r = post(client, lead_payload(email=None, phone=None))
    assert r.status_code == 422 and "valid email address or phone" in r.json()["detail"]
    assert client.get("/api/leads", headers=API).json() == []
    assert len(admin_alerts) == 1 and admin_alerts[0][0].startswith("[REJECTED ENQUIRY]")


def test_bad_secret_does_not_alert_the_admin(client, admin_alerts):
    post(client, lead_payload(email=None, phone=None), headers={"X-Webhook-Secret": "wrong"})
    assert admin_alerts == []


# ------------------------------------------------------------------------- duplicates

def test_repeat_email_updates_instead_of_creating(client):
    first = post(client, lead_payload()).json()
    again = post(client, lead_payload(buying_timeline="6 months", message="Still interested")).json()
    assert again["is_duplicate"] and again["status"] == "updated" and again["lead_id"] == first["lead_id"]
    assert len(client.get("/api/leads", headers=API).json()) == 1
    assert again["assigned_to"] == first["assigned_to"]  # keeps its owner


def test_repeat_phone_with_new_email_is_the_same_lead(client):
    first = post(client, lead_payload()).json()
    again = post(client, lead_payload(email="other@example.com", phone="+92 300 1234567")).json()
    assert again["lead_id"] == first["lead_id"]


def test_repeat_enquiry_does_not_erase_existing_details(client):
    first = post(client, lead_payload()).json()
    post(client, {"full_name": "Ahmed Khan", "email": "ahmed.khan@example.com",
                  "buying_timeline": "within 7 days", "budget": "1 crore"})
    lead = client.get(f"/api/leads/{first['lead_id']}", headers=API).json()
    assert lead["property_type"] == "Residential plot"
    assert lead["preferred_location"] == "Islamabad"
    assert lead["message"] == "Please arrange a viewing."
    assert lead["phone"] == "+923001234567"
    assert lead["priority"] == "Urgent"  # the stored phone resolves the 'Missing phone' flag


def test_unreadable_new_budget_keeps_the_old_one(client):
    first = post(client, lead_payload()).json()
    post(client, lead_payload(budget="negotiable"))
    lead = client.get(f"/api/leads/{first['lead_id']}", headers=API).json()
    assert lead["budget_value"] == 15_000_000


def test_round_robin_alternates_between_active_reps(client):
    owners = [post(client, lead_payload(email=f"l{i}@example.com", phone=f"0300123456{i}")).json()["assigned_to"] for i in range(4)]
    assert owners[0] != owners[1] and owners[0] == owners[2] and owners[1] == owners[3]


# --------------------------------------------------------------------- management API

@pytest.mark.parametrize("path", ["/api/leads", "/api/leads/1", "/api/follow-ups/due", "/api/stats"])
def test_management_api_requires_the_api_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get(path, headers={"X-API-Key": API_KEY}).status_code in (200, 404)


def test_webhook_secret_does_not_unlock_the_management_api(client):
    assert client.get("/api/leads", headers={"X-API-Key": WEBHOOK_SECRET}).status_code == 401


def test_list_hides_raw_payload_and_supports_filters(client):
    post(client, lead_payload())
    post(client, lead_payload(email="b@example.com", phone="03111234567", buying_timeline="1 year"))
    rows = client.get("/api/leads", headers=API).json()
    assert len(rows) == 2 and all("raw_payload" not in r for r in rows)
    assert isinstance(rows[0]["review_reasons"], list)
    urgent = client.get("/api/leads?priority=Urgent", headers=API).json()
    assert [r["priority"] for r in urgent] == ["Urgent"]


def test_unknown_lead_is_404(client):
    assert client.get("/api/leads/999", headers=API).status_code == 404
    assert client.post("/api/leads/999/resync", headers=API).status_code == 404


def test_stats(client):
    post(client, lead_payload())
    post(client, lead_payload(email="b@example.com", phone="03111234567", buying_timeline="1 year"))
    stats = client.get("/api/stats", headers=API).json()
    assert stats["total_leads"] == 2 and stats["open_followups"] == 2
    assert stats["by_priority"] == {"Urgent": 1, "Nurture": 1}


def test_follow_up_tasks_can_be_listed_when_due_and_completed(client, monkeypatch):
    post(client, lead_payload())
    assert client.get("/api/follow-ups/due", headers=API).json() == []  # urgent task is due in 1 hour
    monkeypatch.setattr("app.main.now_local", lambda: now_local().replace(year=2099))
    due = client.get("/api/follow-ups/due", headers=API).json()
    assert len(due) == 1 and due[0]["full_name"] == "Ahmed Khan"
    task_id = due[0]["id"]
    assert client.post(f"/api/follow-ups/{task_id}/complete", headers=API).json()["status"] == "Done"
    assert client.get("/api/follow-ups/due", headers=API).json() == []
    assert client.post(f"/api/follow-ups/{task_id}/complete", headers=API).status_code == 409
    assert client.post("/api/follow-ups/999/complete", headers=API).status_code == 404


# ------------------------------------------------------------------ hardening / startup

def test_oversized_request_is_rejected(set_env, make_client):
    set_env(MAX_REQUEST_BYTES=200)
    c = make_client()
    assert post(c, lead_payload(message="x" * 1000)).status_code == 413


def test_message_over_the_field_limit_is_a_422(client):
    assert post(client, lead_payload(message="x" * 5001)).status_code == 422


def test_production_refuses_to_start_with_weak_secrets(set_env):
    from app.main import app
    set_env(ENVIRONMENT="production", WEBHOOK_SECRET="change-this-secret", API_KEY="short")
    with pytest.raises(RuntimeError, match="WEBHOOK_SECRET"):
        with TestClient(app):
            pass


def test_production_starts_with_strong_secrets(set_env):
    from app.main import app
    set_env(ENVIRONMENT="production", WEBHOOK_SECRET="a" * 32, API_KEY="b" * 32)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_invalid_timezone_refuses_to_start(set_env):
    from app.main import app
    set_env(TIMEZONE="Mars/Olympus")
    with pytest.raises(RuntimeError, match="TIMEZONE"):
        with TestClient(app):
            pass
