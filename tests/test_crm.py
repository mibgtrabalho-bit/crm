from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def signup_login(email: str, company: str, role: str = "DIRECTOR"):
    client.post("/auth/signup", json={"company_name": company, "email": email, "password": "secret123", "role": role})
    token = client.post("/auth/login", json={"email": email, "password": "secret123"}).json()["session_token"]
    return {"x-session-token": token}


def test_transactional_opportunity_and_pipeline_visibility():
    h = signup_login("d1@example.com", "Acme A")
    create = client.post(
        "/opportunities",
        headers=h,
        json={
            "title": "Deal 1",
            "stage": "PROSPECTING",
            "contact": {"name": "Maria Silva", "email": "maria@x.com"},
            "company": {"name": "Cliente XPTO"},
            "deal_value_legacy": 500,
        },
    )
    assert create.status_code == 200
    pipe = client.get("/pipeline", headers=h)
    assert pipe.status_code == 200
    assert len(pipe.json()["items"]) == 1


def test_proposal_requires_deal_value():
    h = signup_login("d2@example.com", "Acme B")
    create = client.post(
        "/opportunities",
        headers=h,
        json={"title": "Deal 2", "stage": "PROSPECTING", "contact": {"name": "Joao"}},
    )
    opp_id = create.json()["id"]
    move = client.patch(f"/opportunities/{opp_id}", headers=h, json={"stage": "PROPOSAL"})
    assert move.status_code == 400


def test_conversion_and_arr_metric_format():
    h = signup_login("d3@example.com", "Acme C")
    now = datetime.utcnow()
    client.post(
        "/opportunities",
        headers=h,
        json={
            "title": "Deal 3",
            "stage": "CLOSED",
            "contact": {"name": "Ana"},
            "implementation_value": 1000,
            "saas_monthly_value": 100,
            "close_date": now.date().isoformat(),
            "first_invoice_month": f"{now.year}-04",
        },
    )
    metrics = client.post(
        "/dashboard/metrics",
        headers=h,
        json={"start": (now - timedelta(days=1)).isoformat(), "end": (now + timedelta(days=1)).isoformat()},
    )
    assert metrics.status_code == 200
    assert metrics.json()["conversion_rate"].endswith("%")
    assert "," in metrics.json()["conversion_rate"]
