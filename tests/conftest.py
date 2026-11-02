import json
import json as jsonlib  # FakeMonday.__call__ has a `json` parameter that shadows the module
import os

import pytest
from fastapi.testclient import TestClient

from app import monday, notifications
from app.config import get_settings
from app.services import load_rules

WEBHOOK_SECRET = "test-webhook-secret-123"
API_KEY = "test-api-key-1234567890"

MONDAY_ENV = {
    "MONDAY_API_TOKEN": "tok_test",
    "MONDAY_BOARD_ID": "111",
    "MONDAY_ACCOUNT_URL": "https://acme.monday.com",
    "MONDAY_EMAIL_COLUMN_ID": "email_col",
    "MONDAY_PHONE_COLUMN_ID": "phone_col",
    "MONDAY_PROPERTY_TYPE_COLUMN_ID": "ptype_col",
    "MONDAY_BUDGET_COLUMN_ID": "budget_col",
    "MONDAY_LOCATION_COLUMN_ID": "loc_col",
    "MONDAY_TIMELINE_COLUMN_ID": "timeline_col",
    "MONDAY_MESSAGE_COLUMN_ID": "msg_col",
    "MONDAY_STAGE_COLUMN_ID": "stage_col",
    "MONDAY_PRIORITY_COLUMN_ID": "prio_col",
    "MONDAY_FOLLOWUP_COLUMN_ID": "due_col",
    "MONDAY_TASK_BOARD_ID": "222",
    "MONDAY_TASK_DUE_COLUMN_ID": "task_due",
    "MONDAY_TASK_NOTES_COLUMN_ID": "task_notes",
}


def reset_caches():
    get_settings.cache_clear()
    load_rules.cache_clear()


@pytest.fixture(autouse=True)
def clean_environment(tmp_path, monkeypatch):
    """Every test gets its own database and none of the developer's real settings."""
    for key in list(os.environ):
        if key.startswith(("MONDAY_", "SMTP_", "SLACK_")) or key in {
            "WEBHOOK_SECRET", "API_KEY", "ENVIRONMENT", "ADMIN_EMAIL", "SALES_REP_EMAIL",
            "DATABASE_URL", "ROUTING_RULES_PATH", "MAX_REQUEST_BYTES", "TIMEZONE", "DEFAULT_COUNTRY_CODE",
        }:
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)  # so a developer's local .env is never read by the tests
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setattr(monday, "_sleep", lambda s: None)  # never actually wait between retries
    reset_caches()
    yield
    reset_caches()


@pytest.fixture
def set_env(monkeypatch):
    def _set(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, str(value))
        reset_caches()
    return _set


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_client():
    """Create a client AFTER the test has changed settings (startup reads them)."""
    from app.main import app
    stack = []

    def _make():
        c = TestClient(app)
        c.__enter__()
        stack.append(c)
        return c

    yield _make
    for c in stack:
        c.__exit__(None, None, None)


@pytest.fixture
def admin_alerts(monkeypatch):
    """Capture admin alerts instead of sending them."""
    sent = []
    monkeypatch.setattr(notifications, "alert_admin", lambda subject, html, text: sent.append((subject, text)))
    return sent


HEADERS = {"X-Webhook-Secret": WEBHOOK_SECRET}
API = {"X-API-Key": API_KEY}


def lead_payload(**overrides):
    payload = {
        "full_name": "Ahmed Khan", "email": "ahmed.khan@example.com", "phone": "0300 1234567",
        "property_type": "Residential plot", "budget": "PKR 1.5 crore", "preferred_location": "Islamabad",
        "buying_timeline": "within 7 days", "message": "Please arrange a viewing.", "source": "website",
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not None}


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeMonday:
    """A tiny in-memory monday.com. Records every GraphQL call; supports scripted failures."""

    def __init__(self):
        self.calls: list[tuple[str, dict, dict]] = []  # (operation, variables, headers)
        self.items: dict[str, dict] = {}  # id -> {"name", "cv"}
        self.notes: list[dict] = []
        self.next_id = 1000
        self.failures: dict[str, list] = {}  # operation -> queue of statuses (int) or error bodies (dict)

    @staticmethod
    def operation(query: str) -> str:
        for name in ("items_page_by_column_values", "create_item", "change_multiple_column_values", "create_update"):
            if name in query:
                return name
        return "unknown"

    def count(self, operation: str) -> int:
        return sum(1 for op, _, _ in self.calls if op == operation)

    def __call__(self, url, headers=None, json=None, timeout=None):
        op = self.operation(json["query"])
        variables = json["variables"]
        self.calls.append((op, variables, headers or {}))
        queue = self.failures.get(op)
        if queue:
            failure = queue.pop(0)
            return FakeResponse(failure) if isinstance(failure, int) else FakeResponse(200, failure)
        if op == "items_page_by_column_values":
            hits = [
                {"id": i, "name": it["name"]} for i, it in self.items.items()
                if it["board"] == variables["boardId"]
                and variables["val"] in [str(v.get("email") if isinstance(v, dict) else v) for v in it["cv"].values()]
            ]
            return FakeResponse(200, {"data": {"items_page_by_column_values": {"items": hits[:1]}}})
        if op == "create_item":
            self.next_id += 1
            item_id = str(self.next_id)
            self.items[item_id] = {"name": variables["name"], "cv": jsonlib.loads(variables["cv"]),
                                   "board": variables["boardId"]}
            return FakeResponse(200, {"data": {"create_item": {"id": item_id}}})
        if op == "change_multiple_column_values":
            self.items[variables["itemId"]]["cv"].update(jsonlib.loads(variables["cv"]))
            return FakeResponse(200, {"data": {"change_multiple_column_values": {"id": variables["itemId"]}}})
        if op == "create_update":
            self.next_id += 1
            self.notes.append({"item": variables["itemId"], "body": variables["body"]})
            return FakeResponse(200, {"data": {"create_update": {"id": str(self.next_id)}}})
        return FakeResponse(400, {"errors": [{"message": "unknown operation"}]})


@pytest.fixture
def fake_monday(monkeypatch, set_env):
    fake = FakeMonday()
    monkeypatch.setattr(monday, "_http_post", fake)
    set_env(**MONDAY_ENV)
    return fake
