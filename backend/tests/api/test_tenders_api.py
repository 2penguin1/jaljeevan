import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models import User

PASSWORD = "demo-pass-123"


@pytest.fixture
def logins():
    tag = uuid.uuid4().hex[:8]
    emails = {"officer": f"officer-{tag}@t.test", "citizen": f"citizen-{tag}@t.test"}
    with SessionLocal() as s:
        s.add(User(email=emails["officer"], password_hash=hash_password(PASSWORD), name="Officer", role="gov_admin"))
        s.add(User(email=emails["citizen"], password_hash=hash_password(PASSWORD), name="Citizen", role="citizen"))
        s.commit()
    yield emails
    with SessionLocal() as s:
        s.query(User).filter(User.email.in_(emails.values())).delete(synchronize_session=False)
        s.commit()


BODY = {"zone_id": str(uuid.uuid4()), "qty_per_day": 100, "duration_days": 30, "price_per_unit": 60, "radius_km": 100}


def test_publishing_needs_a_relief_officer_login(logins):
    with TestClient(app) as c:
        assert c.post("/api/v1/tenders", json=BODY).status_code == 401
        c.post("/api/v1/auth/login", json={"email": logins["citizen"], "password": PASSWORD})
        assert c.post("/api/v1/tenders", json=BODY).status_code == 403
        assert c.get("/api/v1/inbox").status_code == 403
        c.post("/api/v1/auth/login", json={"email": logins["officer"], "password": PASSWORD})
        assert c.post("/api/v1/tenders", json=BODY).status_code == 404  # allowed; the zone does not exist


def test_the_old_shared_demo_code_no_longer_opens_anything():
    with TestClient(app) as c:
        assert c.post("/api/v1/tenders", json=BODY, headers={"X-Admin-Token": "dev-admin-token"}).status_code == 401


def test_reading_is_open_and_unknown_things_say_so():
    with TestClient(app) as c:
        assert c.get("/api/v1/tenders").status_code == 200
        assert c.get("/api/v1/vendors").status_code == 200
        assert c.get(f"/api/v1/zones/{uuid.uuid4()}/relief-need").status_code == 404
        assert c.get(f"/api/v1/tenders/{uuid.uuid4()}").status_code == 404
