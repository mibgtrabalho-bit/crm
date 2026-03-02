from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    role: str = "DIRECTOR"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str
    new_password: str


class ContactInline(BaseModel):
    id: int | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    custom_fields: str | None = None


class CompanyInline(BaseModel):
    name: str
    cnpj: str | None = None
    address: str | None = None
    website: str | None = None


class OpportunityCreateIn(BaseModel):
    title: str
    funnel_id: int | None = None
    assignee_id: int | None = None
    stage: str = "PROSPECTING"
    contact: ContactInline
    company: CompanyInline | None = None
    saas_monthly_value: float | None = None
    implementation_value: float | None = None
    deal_value_legacy: float | None = None
    close_date: date | None = None
    first_invoice_month: str | None = None


class OpportunityUpdateIn(BaseModel):
    title: str | None = None
    stage: str | None = None
    assignee_id: int | None = None
    saas_monthly_value: float | None = None
    implementation_value: float | None = None
    close_date: date | None = None
    first_invoice_month: str | None = None


class DashboardSettingsIn(BaseModel):
    widgets: list[str] = Field(default_factory=list, max_length=4)


class BulkEmailIn(BaseModel):
    contact_ids: list[int]
    template: str


class TargetUpdateIn(BaseModel):
    monthly_target: float


class DateRangeIn(BaseModel):
    start: datetime
    end: datetime
