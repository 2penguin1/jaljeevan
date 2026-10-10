import uuid

from fastapi.testclient import TestClient

from app.main import app

ADMIN = {"X-Admin-Token": "dev-admin-token"}


def test_admin_endpoints_require_token():
    with TestClient(app) as c:
        assert c.post("/admin/pipeline/run").status_code == 401
        assert c.get("/admin/pipeline/runs").status_code == 401


def test_trigger_creates_run_and_schedules_job(monkeypatch):
    scheduled = []
    with TestClient(app) as c:
        monkeypatch.setattr(app.state.container, "run_pipeline_job", lambda run_id: scheduled.append(run_id))
        res = c.post("/admin/pipeline/run", headers=ADMIN)
        assert res.status_code == 202
        run_id = res.json()["run_id"]
        assert scheduled == [uuid.UUID(run_id)]
        runs = c.get("/admin/pipeline/runs", headers=ADMIN).json()
        assert any(r["id"] == run_id for r in runs)
        one = c.get(f"/admin/pipeline/runs/{run_id}", headers=ADMIN)
        assert one.status_code == 200 and one.json()["kind"] == "local"


def test_missing_run_maps_not_found_error_to_404():
    with TestClient(app) as c:
        res = c.get(f"/admin/pipeline/runs/{uuid.uuid4()}", headers=ADMIN)
    assert res.status_code == 404 and res.json()["detail"].startswith("pipeline run")
