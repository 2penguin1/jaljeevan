import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_brief_writes_need_an_officer_and_drafts_are_not_public():
    with TestClient(app) as c:
        assert c.post(f"/api/v1/zones/{uuid.uuid4()}/briefs").status_code == 401
        assert c.get("/api/v1/briefs").status_code == 401
        assert c.post(f"/api/v1/briefs/{uuid.uuid4()}/approve").status_code == 401
        assert c.get(f"/api/v1/briefs/{uuid.uuid4()}").status_code == 404
        res = c.get(f"/api/v1/zones/{uuid.uuid4()}/brief")
        assert res.status_code == 200 and res.json() is None
