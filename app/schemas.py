from pydantic import BaseModel, EmailStr, Field, ConfigDict

class LeadIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    property_type: str | None = None
    budget: str | int | float | None = None
    preferred_location: str | None = None
    buying_timeline: str | None = None
    message: str | None = Field(default=None, max_length=5000)
    source: str = "website"
    secret: str | None = None

class LeadResult(BaseModel):
    lead_id: int
    status: str
    priority: str
    assigned_to: str
    follow_up_due: str
    is_duplicate: bool
    message: str
    crm_synced: bool = False
    warnings: list[str] = []
