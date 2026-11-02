"""Application settings, loaded from environment variables or a local .env file."""
import re
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that ship in examples/docs and must never be used as a real secret in production.
PLACEHOLDER_SECRETS = {
    "change-this-secret",
    "change-me",
    "changeme",
    "secret",
    "replace-with-a-long-random-secret",
    "replace-with-your-webhook-secret",
    "replace-with-a-long-random-api-key",
    "change-me-to-a-long-random-string",
}
MIN_SECRET_LENGTH = 16


class Settings(BaseSettings):
    app_name: str = "Techtox Lead Response Agent"
    environment: str = "development"  # set to "production" on a real deployment
    log_level: str = "INFO"

    # Authentication
    webhook_secret: str = ""  # shared secret for POST /webhooks/leads
    api_key: str = ""  # key for the /api/* management endpoints (X-API-Key header)

    # Storage / locale
    database_url: str = "sqlite:///./data/leads.db"
    routing_rules_path: str = ""  # optional override for config/routing_rules.json
    default_country_code: str = "+92"
    timezone: str = "Asia/Karachi"
    max_request_bytes: int = 65536

    # monday.com
    monday_api_token: str = ""
    monday_api_url: str = "https://api.monday.com/v2"
    monday_api_version: str = ""  # empty = monday's current default version
    monday_account_url: str = ""  # e.g. https://your-account.monday.com (for links in emails)
    monday_board_id: str = ""
    monday_group_id: str = "topics"
    monday_email_column_id: str = ""
    monday_phone_column_id: str = ""
    monday_property_type_column_id: str = ""
    monday_budget_column_id: str = ""
    monday_location_column_id: str = ""
    monday_timeline_column_id: str = ""
    monday_message_column_id: str = ""
    monday_stage_column_id: str = ""
    monday_priority_column_id: str = ""
    monday_followup_column_id: str = ""
    monday_owner_column_id: str = ""  # optional People column
    monday_task_board_id: str = ""  # optional separate Follow-up Tasks board
    monday_task_group_id: str = "topics"
    monday_task_due_column_id: str = ""
    monday_task_notes_column_id: str = ""

    # Email (SMTP) and Slack
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    sales_rep_email: str = ""  # fallback recipient when a rep has no email
    admin_email: str = ""  # receives rejected-lead and failure alerts
    slack_webhook_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _weak_secret(value: str) -> bool:
    return not value or value.lower() in PLACEHOLDER_SECRETS or len(value) < MIN_SECRET_LENGTH


def startup_problems(s: Settings) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors must stop the app from starting."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        ZoneInfo(s.timezone)
    except Exception:
        errors.append(f"TIMEZONE '{s.timezone}' is not a valid IANA time zone (e.g. Asia/Karachi).")
    if not re.fullmatch(r"\+[1-9]\d{0,3}", s.default_country_code):
        errors.append("DEFAULT_COUNTRY_CODE must look like +92.")

    if s.is_production:
        if _weak_secret(s.webhook_secret):
            errors.append(f"WEBHOOK_SECRET must be a random value of at least {MIN_SECRET_LENGTH} characters in production.")
        if _weak_secret(s.api_key):
            errors.append(f"API_KEY must be a random value of at least {MIN_SECRET_LENGTH} characters in production.")
    else:
        if not s.webhook_secret:
            warnings.append("WEBHOOK_SECRET is empty: the webhook accepts unauthenticated requests (development only).")
        if not s.api_key:
            warnings.append("API_KEY is empty: /api/* endpoints are open (development only).")

    if s.monday_api_token and not s.monday_board_id:
        warnings.append("MONDAY_API_TOKEN is set but MONDAY_BOARD_ID is empty: monday.com sync is disabled.")
    if s.smtp_host and not (s.smtp_from_email or s.smtp_username):
        warnings.append("SMTP_HOST is set but SMTP_FROM_EMAIL is empty: emails cannot be sent.")
    if s.smtp_host and not s.admin_email:
        warnings.append("ADMIN_EMAIL is empty: rejected-lead and failure alerts will only appear in the logs.")
    return errors, warnings
