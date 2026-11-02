"""Request and response models.

LeadIn is deliberately tolerant: validation of the *business* rules (valid email, valid
phone, readable budget) happens in app.services.normalize_lead so that a lead with one
bad field is kept and flagged for review instead of being rejected outright, exactly like
the n8n workflow. Field aliases accept snake_case, the camelCase keys the Google Apps
Script sends, and Google Form column titles.
"""
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


def _names(snake: str, camel: str, title: str) -> AliasChoices:
    # For single-word fields snake == camel, so duplicates are dropped.
    return AliasChoices(*dict.fromkeys((snake, camel, title)))


class LeadIn(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",
        coerce_numbers_to_str=True,  # Google Forms / Sheets often send phone and budget as numbers
        populate_by_name=True,
    )
    full_name: str | None = Field(default=None, max_length=160, validation_alias=_names("full_name", "fullName", "Full Name"))
    email: str | None = Field(default=None, max_length=254, validation_alias=_names("email", "Email", "email"))
    phone: str | None = Field(default=None, max_length=40, validation_alias=_names("phone", "Phone", "phone"))
    property_type: str | None = Field(default=None, max_length=120, validation_alias=_names("property_type", "propertyType", "Property Type"))
    budget: str | None = Field(default=None, max_length=80, validation_alias=_names("budget", "Budget", "budget"))
    preferred_location: str | None = Field(default=None, max_length=200, validation_alias=_names("preferred_location", "preferredLocation", "Preferred Location"))
    buying_timeline: str | None = Field(default=None, max_length=120, validation_alias=_names("buying_timeline", "buyingTimeline", "Buying Timeline"))
    message: str | None = Field(default=None, max_length=5000, validation_alias=_names("message", "Message", "message"))
    source: str | None = Field(default=None, max_length=80, validation_alias=_names("source", "Source", "Lead Source"))
    submitted_at: str | None = Field(default=None, max_length=64, validation_alias=_names("submitted_at", "submittedAt", "Timestamp"))
    secret: str | None = Field(default=None, max_length=256)


class LeadResult(BaseModel):
    lead_id: int
    status: str  # "created" or "updated"
    priority: str
    assigned_to: str
    follow_up_due: str
    follow_up_action: str
    is_duplicate: bool
    crm_status: str  # "queued" (monday.com sync running in the background) or "not_configured"
    message: str
    warnings: list[str] = Field(default_factory=list)
