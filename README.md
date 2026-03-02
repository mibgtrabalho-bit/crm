# Multi-tenant Sales CRM (incremental implementation)

This repository now contains a minimal FastAPI CRM implementing tenant isolation by `COMPANY`, role-scoped visibility, pipeline stages, transactional opportunity creation, dashboard metrics, targets, and bulk email logs.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[test]
uvicorn app.main:app --reload
```

## API highlights

- `POST /auth/signup`, `POST /auth/login`, password reset endpoints.
- `POST /opportunities` creates Opportunity + inline Contact (+ optional Account Company) in one DB transaction.
- `GET /pipeline?view=kanban|list` returns tenant-scoped data with empty-state and error handling.
- `PATCH /opportunities/{id}` allows pipeline modal-style edits and enforces stage validation (`PROPOSAL` requires value).
- `POST /dashboard/settings` stores up to 4 widgets.
- `POST /dashboard/metrics` computes CLOSED/NEGOTIATION metrics, conversion (using `first_closed_at`), SaaS/implementation totals, and ARR.
- `PATCH /users/{id}/target` for manager/director quota assignment.
- `POST /contacts/bulk-email` with `{{first_name}}`/`{{name}}` substitution and per-company/per-contact logs.

## How to test checklist (Change 1: auth + tenant + roles)

- [ ] Sign up two different companies and log in.
- [ ] Verify one tenant cannot list another tenant's contacts/opportunities.
- [ ] Verify Sales Rep only sees own/assigned opportunities, Manager team scope, Director full tenant scope.

## How to test checklist (Change 2: pipeline + creation speed + edit)

- [ ] Create opportunity with inline contact; confirm success.
- [ ] Try creating without contact; confirm blocked.
- [ ] Move stage to `PROPOSAL` without values; confirm blocked.
- [ ] Edit opportunity via patch endpoint and verify pipeline reflects updates immediately.

## How to test checklist (Change 3: dashboards + metrics + quotas + bulk email)

- [ ] Save dashboard settings with <=4 widgets; test >4 fails.
- [ ] Create CLOSED and NEGOTIATION deals; verify dashboard metrics.
- [ ] Validate conversion format uses comma decimal (`12,3%`) and 0,0% when no created deals.
- [ ] Set monthly target as Manager/Director; ensure Sales Rep cannot.
- [ ] Send bulk email and check logs were created.

## Tests

```bash
pytest -q
```
