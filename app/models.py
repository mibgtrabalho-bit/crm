from datetime import datetime, date
from enum import Enum
from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Date,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Role(str, Enum):
    SALES_REP = "SALES_REP"
    MANAGER = "MANAGER"
    DIRECTOR = "DIRECTOR"


class Stage(str, Enum):
    PROSPECTING = "PROSPECTING"
    FOLLOW_UP = "FOLLOW_UP"
    SCHEDULE = "SCHEDULE"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED = "CLOSED"
    LOST = "LOST"


class CompanyTier(Base):
    __tablename__ = "company_tiers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    min_users: Mapped[int] = mapped_column(Integer)
    max_users: Mapped[int] = mapped_column(Integer)


class TenantCompany(Base):
    __tablename__ = "tenant_companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    tier_id: Mapped[int | None] = mapped_column(ForeignKey("company_tiers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    reset_token: Mapped[str | None] = mapped_column(String, nullable=True)
    monthly_target: Mapped[float] = mapped_column(Float, default=0)


class Funnel(Base):
    __tablename__ = "funnels"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_fields: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountCompany(Base):
    __tablename__ = "account_companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    cnpj: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("company_id", "id", name="uq_opportunity_company_id_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    funnel_id: Mapped[int | None] = mapped_column(ForeignKey("funnels.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    account_company_id: Mapped[int | None] = mapped_column(ForeignKey("account_companies.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String, default=Stage.PROSPECTING.value)
    deal_value_legacy: Mapped[float | None] = mapped_column(Float, nullable=True)
    saas_monthly_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    implementation_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_invoice_month: Mapped[str | None] = mapped_column(String, nullable=True)
    first_closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserDashboardSettings(Base):
    __tablename__ = "user_dashboard_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    widgets_csv: Mapped[str] = mapped_column(String, default="")


class OutboundEmailLog(Base):
    __tablename__ = "outbound_email_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tenant_companies.id"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    template: Mapped[str] = mapped_column(Text)
    body_sent: Mapped[str] = mapped_column(Text)
    sent_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
