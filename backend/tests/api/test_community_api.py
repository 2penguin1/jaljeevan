import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_community_reads_are_open_and_writes_need_an_account():
    with TestClient(app) as c:
        assert c.get("/api/v1/campaigns").status_code == 200
        assert c.get("/api/v1/volunteer-tasks").status_code == 200
        assert c.post("/api/v1/campaigns", json={"title": "x", "story": "", "goal_inr": 100}).status_code == 401
        assert c.post(f"/api/v1/campaigns/{uuid.uuid4()}/pledges", json={"amount_inr": 100}).status_code == 401
        assert c.post(f"/api/v1/volunteer-tasks/{uuid.uuid4()}/signups").status_code == 401
