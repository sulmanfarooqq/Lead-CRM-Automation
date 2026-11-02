from app import notifications
from tests.conftest import API, HEADERS, lead_payload


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.sent, self.tls, self.login_args = host, port, [], False, None
        FakeSMTP.instances.append(self)

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, context=None): self.tls = True
    def login(self, user, password): self.login_args = (user, password)
    def send_message(self, msg): self.sent.append(msg)


class BrokenSMTP(FakeSMTP):
    def send_message(self, msg):
        raise OSError("connection refused")


def smtp_env(set_env, **extra):
    set_env(SMTP_HOST="smtp.test", SMTP_FROM_EMAIL="agent@test.io", SMTP_USERNAME="u", SMTP_PASSWORD="p",
            SALES_REP_EMAIL="fallback@test.io", ADMIN_EMAIL="admin@test.io", **extra)


def post(client, payload=None):
    return client.post("/webhooks/leads", json=payload or lead_payload(), headers=HEADERS)


def test_rep_gets_an_html_and_text_email(client, set_env, monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    smtp_env(set_env)
    post(client)
    smtp = FakeSMTP.instances[0]
    msg = smtp.sent[0]
    assert smtp.tls and smtp.login_args == ("u", "p")
    assert msg["Subject"] == "[URGENT] New lead: Ahmed Khan"
    assert msg["To"] == "fallback@test.io"  # sample example.com rep addresses fall back to SALES_REP_EMAIL
    assert "Ahmed Khan" in msg.get_body(("plain",)).get_content()
    assert "<table" in msg.get_body(("html",)).get_content()
    assert "not been contacted" in msg.get_body(("plain",)).get_content()


def test_repeat_enquiry_subject(client, set_env, monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    smtp_env(set_env)
    post(client)
    post(client)
    assert [i.sent[0]["Subject"] for i in FakeSMTP.instances][-1] == "[URGENT] Repeat enquiry: Ahmed Khan"


def test_email_html_escapes_buyer_input(client, set_env, monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    smtp_env(set_env)
    post(client, lead_payload(full_name="<b>Eve</b>", message="<img src=x onerror=alert(1)>"))
    html_part = FakeSMTP.instances[0].sent[0].get_body(("html",)).get_content()
    assert "<img" not in html_part and "&lt;img" in html_part


def test_ssl_port_uses_smtp_ssl(client, set_env, monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP_SSL", FakeSMTP)
    smtp_env(set_env, SMTP_PORT=465)
    post(client)
    assert FakeSMTP.instances[0].port == 465 and FakeSMTP.instances[0].tls is False and FakeSMTP.instances[0].sent


def test_slack_message_is_posted(client, set_env, monkeypatch):
    calls = []

    class Ok:
        def raise_for_status(self): pass

    monkeypatch.setattr(notifications, "_http_post", lambda url, json=None, timeout=None: calls.append((url, json)) or Ok())
    set_env(SLACK_WEBHOOK_URL="https://hooks.slack.test/abc")
    post(client)
    assert calls[0][0] == "https://hooks.slack.test/abc"
    assert "[URGENT] New lead: Ahmed Khan" in calls[0][1]["text"]


def test_delivery_failure_alerts_the_admin_without_losing_the_lead(client, set_env, monkeypatch, admin_alerts):
    monkeypatch.setattr(notifications.smtplib, "SMTP", BrokenSMTP)
    smtp_env(set_env)
    r = post(client)
    assert r.status_code == 200
    assert client.get(f"/api/leads/{r.json()['lead_id']}", headers=API).status_code == 200
    assert any("Notify sales team" in s for s, _ in admin_alerts)


def test_no_channels_configured_is_only_a_log_warning(client, admin_alerts, caplog):
    with caplog.at_level("WARNING"):
        assert post(client).status_code == 200
    assert admin_alerts == [] and "no team notification channel" in caplog.text


def test_admin_alert_reaches_the_admin_mailbox(client, set_env, monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    smtp_env(set_env)
    post(client, lead_payload(email=None, phone=None))
    msg = FakeSMTP.instances[0].sent[0]
    assert msg["To"] == "admin@test.io" and msg["Subject"].startswith("[REJECTED ENQUIRY]")
