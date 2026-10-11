import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_writing_a_tender_needs_the_demo_access_code():
    body = {"zone_id": str(uuid.uuid4()), "qty_per_day": 100, "duration_days": 30, "price_per_unit": 60,
            "radius_km": 100}
    with TestClient(app) as c:
        assert c.post("/api/v1/tenders", json=body).status_code in (401, 403)
        assert c.post("/api/v1/tenders", json=body, headers={"X-Admin-Token": "dev-admin-token"}).status_code == 404


def test_reading_is_open_and_unknown_things_say_so():
    with TestClient(app) as c:
        assert c.get("/api/v1/tenders").status_code == 200
        assert c.get("/api/v1/vendors").status_code == 200
        assert c.get(f"/api/v1/zones/{uuid.uuid4()}/relief-need").status_code == 404
        assert c.get(f"/api/v1/tenders/{uuid.uuid4()}").status_code == 404
