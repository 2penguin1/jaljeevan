import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_plan_writes_need_an_officer_and_drafts_are_not_public():
    with TestClient(app) as c:
        assert c.post(f"/api/v1/zones/{uuid.uuid4()}/plans").status_code == 401
        assert c.get("/api/v1/plans").status_code == 401
        assert c.post(f"/api/v1/plans/{uuid.uuid4()}/approve").status_code == 401
        assert c.get(f"/api/v1/plans/{uuid.uuid4()}").status_code == 404
        assert c.get(f"/api/v1/zones/{uuid.uuid4()}/plan").json() is None
