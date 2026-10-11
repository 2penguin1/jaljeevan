import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models import Organization, User

PASSWORD = "demo-pass-123"


@pytest.fixture
def accounts():
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        vendor_org = Organization(kind="vendor", name=f"Test Tankers {tag}", state_code="MH")
        s.add(vendor_org)
        s.flush()
        users = {
            "officer": User(email=f"officer-{tag}@t.test", password_hash=hash_password(PASSWORD), name="Officer",
                            role="gov_admin"),
            "vendor": User(email=f"vendor-{tag}@t.test", password_hash=hash_password(PASSWORD), name="Vendor",
                           role="vendor", org_id=vendor_org.id),
        }
        s.add_all(users.values())
        s.commit()
        emails = {k: u.email for k, u in users.items()}
        org_id = vendor_org.id
    yield emails
    with SessionLocal() as s:
        s.query(User).filter(User.email.like(f"%{tag}%")).delete(synchronize_session=False)
        s.query(Organization).filter(Organization.id == org_id).delete()
        s.commit()


def test_login_sets_a_private_cookie_and_me_tells_who_you_are(accounts):
    with TestClient(app) as c:
        res = c.post("/api/v1/auth/login", json={"email": accounts["vendor"].upper(), "password": PASSWORD})
        assert res.status_code == 200 and res.json()["role"] == "vendor"
        cookie = res.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        me = c.get("/api/v1/auth/me").json()
        assert me["email"] == accounts["vendor"] and me["org_name"].startswith("Test Tankers")
        assert c.post("/api/v1/auth/logout").status_code == 204
        assert c.get("/api/v1/auth/me").status_code == 401


def test_a_wrong_password_is_refused_and_guessing_is_braked(accounts):
    with TestClient(app) as c:
        ip = {"X-Forwarded-For": "7.7.7.7"}
        for _ in range(5):
            assert c.post("/api/v1/auth/login", json={"email": accounts["officer"], "password": "nope"}, headers=ip).status_code == 401
        assert c.post("/api/v1/auth/login", json={"email": accounts["officer"], "password": PASSWORD}, headers=ip).status_code == 429


def test_signup_always_makes_a_citizen_whatever_the_request_says():
    email = f"citizen-{uuid.uuid4().hex[:8]}@example.org"
    try:
        with TestClient(app) as c:
            res = c.post("/api/v1/auth/signup", json={"email": email, "name": "Asha", "password": "long-enough-1",
                                                      "role": "gov_admin", "org_id": str(uuid.uuid4())})
            assert res.status_code == 201 and res.json()["role"] == "citizen" and res.json()["org_id"] is None
            assert c.post("/api/v1/auth/signup", json={"email": email, "name": "A", "password": "long-enough-1"}).status_code == 409
            assert c.post("/api/v1/auth/signup", json={"email": "x@example.org", "name": "A", "password": "short"}).status_code == 422
    finally:
        with SessionLocal() as s:
            s.query(User).filter(User.email == email).delete()
            s.commit()


def test_a_forged_cookie_is_not_a_session():
    with TestClient(app) as c:
        c.cookies.set("session", "not-a-real-token")
        assert c.get("/api/v1/auth/me").status_code == 401


def test_spaces_and_capitals_do_not_get_extra_guesses(accounts):
    with TestClient(app) as c:
        for variant in (accounts["officer"], " " + accounts["officer"], accounts["officer"].upper() + "  ",
                        "\t" + accounts["officer"], accounts["officer"] + " "):
            c.post("/api/v1/auth/login", json={"email": variant, "password": "nope"}, headers={"X-Forwarded-For": "9.9.9.9"})
        res = c.post("/api/v1/auth/login", json={"email": accounts["officer"], "password": PASSWORD},
                     headers={"X-Forwarded-For": "9.9.9.9"})
        assert res.status_code == 429
        other = c.post("/api/v1/auth/login", json={"email": accounts["officer"], "password": PASSWORD},
                       headers={"X-Forwarded-For": "8.8.8.8"})
        assert other.status_code == 200  # the real officer, from another address, still gets in


def test_too_long_passwords_get_a_clear_answer_not_a_crash():
    with TestClient(app) as c:
        res = c.post("/api/v1/auth/signup", json={"email": "long@example.org", "name": "A", "password": "x" * 80})
        assert res.status_code == 422


def test_a_rejected_password_is_never_echoed_back():
    with TestClient(app) as c:
        res = c.post("/api/v1/auth/signup", json={"email": "e@example.org", "name": "A", "password": "Zq9!x"})
        assert res.status_code == 422 and "Zq9!x" not in res.text
