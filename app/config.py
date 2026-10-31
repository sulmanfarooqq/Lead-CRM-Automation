from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Techtox Lead Response Agent"
    environment: str = "development"
    webhook_secret: str = "change-this-secret"
    database_url: str = "sqlite:///./data/leads.db"
    default_country_code: str = "+92"
    timezone: str = "Asia/Karachi"
    monday_api_token: str = ""
    monday_api_url: str = "https://api.monday.com/v2"
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
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    sales_rep_email: str = ""
    smtp_use_tls: bool = True
    slack_webhook_url: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
