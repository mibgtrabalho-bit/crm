from datetime import datetime, date
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.auth import create_session, current_user, hash_password, verify_password
from app.database import Base, engine, get_db
from app.models import (
    AccountCompany,
    CompanyTier,
    Contact,
    Funnel,
    Opportunity,
    OutboundEmailLog,
    Role,
    Stage,
    Team,
    TenantCompany,
    User,
    UserDashboardSettings,
)
from app.schemas import (
    BulkEmailIn,
    DashboardSettingsIn,
    DateRangeIn,
    LoginIn,
    OpportunityCreateIn,
    OpportunityUpdateIn,
    ResetConfirmIn,
    ResetRequestIn,
    SignupIn,
    TargetUpdateIn,
)

app = FastAPI(title="Multi-tenant CRM")
Base.metadata.create_all(bind=engine)

ALLOWED_WIDGETS = {
    "CLOSED_SALES",
    "PROJECTED_SALES",
    "CONVERSION_RATE",
    "SAAS_SALES",
    "IMPLEMENTATION_SALES",
    "ARR",
}


def role_scope_filter(user: User):
    if user.role == Role.DIRECTOR.value:
        return True
    if user.role == Role.MANAGER.value:
        return Opportunity.assignee_id.in_(
            [row[0] for row in user_scoped_user_ids(user)]
        )
    return or_(Opportunity.owner_id == user.id, Opportunity.assignee_id == user.id)


def user_scoped_user_ids(user: User):
    # Director sees all users in tenant. Managers see their own team.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        q = db.query(User.id).filter(User.company_id == user.company_id)
        if user.role == Role.MANAGER.value and user.team_id:
            q = q.filter(User.team_id == user.team_id)
        return q.all()
    finally:
        db.close()


def assert_can_edit(user: User, opp: Opportunity):
    if user.role == Role.DIRECTOR.value:
        return
    if user.role == Role.MANAGER.value:
        ids = [u[0] for u in user_scoped_user_ids(user)]
        if opp.assignee_id in ids:
            return
    if opp.owner_id == user.id or opp.assignee_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Permission denied")


@app.post("/auth/signup")
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    tier = db.query(CompanyTier).filter(CompanyTier.name == "starter").first()
    if not tier:
        tier = CompanyTier(name="starter", min_users=1, max_users=10)
        db.add(tier)
        db.flush()
    tenant = TenantCompany(name=payload.company_name, tier_id=tier.id)
    db.add(tenant)
    db.flush()
    team = Team(company_id=tenant.id, name="Prospecting")
    db.add(team)
    db.flush()
    user = User(
        company_id=tenant.id,
        team_id=team.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    return {"ok": True}


@app.post("/auth/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"session_token": create_session(user.id)}


@app.post("/auth/password-reset/request")
def password_reset_request(payload: ResetRequestIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        user.reset_token = create_session(user.id)
        db.commit()
    return {"ok": True}


@app.post("/auth/password-reset/confirm")
def password_reset_confirm(payload: ResetConfirmIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == payload.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    db.commit()
    return {"ok": True}


@app.post("/opportunities")
def create_opportunity(payload: OpportunityCreateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.contact.id is None and not payload.contact.name:
        raise HTTPException(status_code=400, detail="Contact is required")
    with db.begin_nested():
        contact_id = payload.contact.id
        if not contact_id:
            contact = Contact(
                company_id=user.company_id,
                name=payload.contact.name or "",
                email=payload.contact.email,
                phone=payload.contact.phone,
                custom_fields=payload.contact.custom_fields,
            )
            db.add(contact)
            db.flush()
            contact_id = contact.id

        account_company_id = None
        if payload.company:
            if not contact_id:
                raise HTTPException(status_code=400, detail="Company requires at least one contact")
            acc = AccountCompany(
                tenant_id=user.company_id,
                name=payload.company.name,
                cnpj=payload.company.cnpj,
                address=payload.company.address,
                website=payload.company.website,
            )
            db.add(acc)
            db.flush()
            account_company_id = acc.id

        impl_value = payload.implementation_value
        if impl_value is None and payload.deal_value_legacy is not None:
            impl_value = payload.deal_value_legacy

        opp = Opportunity(
            company_id=user.company_id,
            funnel_id=payload.funnel_id,
            title=payload.title,
            contact_id=contact_id,
            account_company_id=account_company_id,
            owner_id=user.id,
            assignee_id=payload.assignee_id or user.id,
            stage=payload.stage,
            deal_value_legacy=payload.deal_value_legacy,
            saas_monthly_value=payload.saas_monthly_value,
            implementation_value=impl_value,
            close_date=payload.close_date,
            first_invoice_month=payload.first_invoice_month,
        )
        if opp.stage == Stage.CLOSED.value and not opp.first_closed_at:
            opp.first_closed_at = datetime.utcnow()
        db.add(opp)
    db.commit()
    db.refresh(opp)
    return {"id": opp.id}


@app.get("/pipeline")
def pipeline(funnel_id: int | None = None, view: str = "kanban", user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        q = db.query(Opportunity).filter(Opportunity.company_id == user.company_id)
        if funnel_id:
            q = q.filter(Opportunity.funnel_id == funnel_id)
        scope = role_scope_filter(user)
        if scope is not True:
            q = q.filter(scope)
        opportunities = q.order_by(Opportunity.created_at.desc()).all()
        if not opportunities:
            return {"view": view, "empty_state": "No opportunities yet", "items": []}
        return {
            "view": view,
            "items": [
                {
                    "id": o.id,
                    "title": o.title,
                    "stage": o.stage,
                    "assignee_id": o.assignee_id,
                    "deal_display": f"Impl: {o.implementation_value or 0:.2f} | SaaS: {o.saas_monthly_value or 0:.2f}/mo",
                }
                for o in opportunities
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline load failed: {exc}")


@app.patch("/opportunities/{opp_id}")
def edit_opportunity(opp_id: int, payload: OpportunityUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(and_(Opportunity.id == opp_id, Opportunity.company_id == user.company_id)).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Not found")
    assert_can_edit(user, opp)

    updates = payload.model_dump(exclude_unset=True)
    next_stage = updates.get("stage", opp.stage)
    next_impl_value = updates.get("implementation_value", opp.implementation_value)
    if next_stage == Stage.PROPOSAL.value and (next_impl_value is None and opp.deal_value_legacy is None):
        raise HTTPException(status_code=400, detail="PROPOSAL requires a deal value")

    for key, value in updates.items():
        setattr(opp, key, value)
    if opp.implementation_value is None and opp.deal_value_legacy is not None:
        opp.implementation_value = opp.deal_value_legacy
    if opp.stage == Stage.CLOSED.value and opp.first_closed_at is None:
        opp.first_closed_at = datetime.utcnow()
    db.commit()
    db.refresh(opp)
    return {"id": opp.id, "stage": opp.stage, "title": opp.title}


@app.post("/dashboard/settings")
def dashboard_settings(payload: DashboardSettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if len(payload.widgets) > 4:
        raise HTTPException(status_code=400, detail="Up to 4 widgets")
    if any(w not in ALLOWED_WIDGETS for w in payload.widgets):
        raise HTTPException(status_code=400, detail="Unknown widget")
    settings = db.query(UserDashboardSettings).filter(UserDashboardSettings.user_id == user.id).first()
    if not settings:
        settings = UserDashboardSettings(user_id=user.id, widgets_csv=",".join(payload.widgets))
        db.add(settings)
    else:
        settings.widgets_csv = ",".join(payload.widgets)
    db.commit()
    return {"widgets": payload.widgets}


def months_remaining(close_date: date | None, first_invoice_month: str | None) -> int:
    if first_invoice_month:
        month = int(first_invoice_month.split("-")[1])
        return max(0, 12 - month + 1)
    if close_date:
        month = close_date.month + 1
        if month > 12:
            return 0
        return 12 - month + 1
    return 12


@app.post("/dashboard/metrics")
def dashboard_metrics(payload: DateRangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Opportunity).filter(Opportunity.company_id == user.company_id)
    scope = role_scope_filter(user)
    if scope is not True:
        q = q.filter(scope)
    total_created = q.filter(and_(Opportunity.created_at >= payload.start, Opportunity.created_at <= payload.end)).count()

    closed = q.filter(
        and_(Opportunity.first_closed_at.is_not(None), Opportunity.first_closed_at >= payload.start, Opportunity.first_closed_at <= payload.end)
    ).all()
    closed_count = len(closed)
    conversion = 0.0 if total_created == 0 else (closed_count / total_created) * 100

    closed_sales = sum((o.implementation_value or o.deal_value_legacy or 0) + (o.saas_monthly_value or 0) for o in closed)
    projected = sum((o.implementation_value or o.deal_value_legacy or 0) + (o.saas_monthly_value or 0) for o in q.filter(Opportunity.stage == Stage.NEGOTIATION.value).all())
    saas_sales = sum((o.saas_monthly_value or 0) for o in closed)
    impl_sales = sum((o.implementation_value or o.deal_value_legacy or 0) for o in closed)
    arr = sum((o.implementation_value or o.deal_value_legacy or 0) + ((o.saas_monthly_value or 0) * months_remaining(o.close_date, o.first_invoice_month)) for o in closed)

    return {
        "closed_sales": closed_sales,
        "projected_sales": projected,
        "conversion_rate": f"{conversion:.1f}".replace(".", ",") + "%",
        "saas_sales": saas_sales,
        "implementation_sales": impl_sales,
        "arr": arr,
    }


@app.patch("/users/{user_id}/target")
def set_target(user_id: int, payload: TargetUpdateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in [Role.MANAGER.value, Role.DIRECTOR.value]:
        raise HTTPException(status_code=403, detail="Permission denied")
    target_user = db.query(User).filter(and_(User.id == user_id, User.company_id == user.company_id)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == Role.MANAGER.value and user.team_id != target_user.team_id:
        raise HTTPException(status_code=403, detail="Outside team scope")
    target_user.monthly_target = payload.monthly_target
    db.commit()
    return {"ok": True}


@app.post("/contacts/bulk-email")
def bulk_email(payload: BulkEmailIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(and_(Contact.company_id == user.company_id, Contact.id.in_(payload.contact_ids))).all()
    sent = 0
    for c in contacts:
        body = payload.template.replace("{{first_name}}", c.name.split(" ")[0]).replace("{{name}}", c.name)
        db.add(
            OutboundEmailLog(
                company_id=user.company_id,
                contact_id=c.id,
                template=payload.template,
                body_sent=body,
                sent_by_user_id=user.id,
            )
        )
        sent += 1
    db.commit()
    return {"sent": sent}


@app.get("/contacts")
def list_contacts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    contacts = db.query(Contact).filter(Contact.company_id == user.company_id).all()
    return [{"id": c.id, "name": c.name, "email": c.email} for c in contacts]


@app.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    settings = db.query(UserDashboardSettings).filter(UserDashboardSettings.user_id == user.id).first()
    widgets = settings.widgets_csv.split(",") if settings and settings.widgets_csv else []
    return {"widgets": widgets, "tables_hidden": ["Contact", "Opportunities"]}
