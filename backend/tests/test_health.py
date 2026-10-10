from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_postgis():
    with TestClient(app) as client:
        res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["postgis"].startswith("3.")
