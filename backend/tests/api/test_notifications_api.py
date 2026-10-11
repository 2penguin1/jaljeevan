import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models import Notification, User

PASSWORD = "demo-pass-123"


@pytest.fixture
def two_users():
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        a = User(email=f"a-{tag}@t.test", password_hash=hash_password(PASSWORD), name="A", role="vendor")
        b = User(email=f"b-{tag}@t.test", password_hash=hash_password(PASSWORD), name="B", role="vendor")
        s.add_all([a, b])
        s.flush()
        s.add_all([Notification(user_id=a.id, kind="bid_update", payload={"text": "for A", "link": "/tenders/x"}),
                   Notification(user_id=b.id, kind="bid_update", payload={"text": "for B", "link": "/tenders/y"})])
        s.commit()
        ids = (a.id, b.id)
        emails = (a.email, b.email)
    yield emails
    with SessionLocal() as s:
        s.query(Notification).filter(Notification.user_id.in_(ids)).delete(synchronize_session=False)
        s.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        s.commit()


def test_each_user_sees_only_their_own_notifications_and_can_mark_them_read(two_users):
    with TestClient(app) as c:
        assert c.get("/api/v1/notifications").status_code == 401
        c.post("/api/v1/auth/login", json={"email": two_users[0], "password": PASSWORD})
        mine = c.get("/api/v1/notifications").json()
        assert mine["unread"] == 1 and [i["text"] for i in mine["items"]] == ["for A"]
        assert c.post("/api/v1/notifications/read", json={}).status_code == 204
        assert c.get("/api/v1/notifications").json()["unread"] == 0
        c.post("/api/v1/auth/login", json={"email": two_users[1], "password": PASSWORD})
        assert c.get("/api/v1/notifications").json()["unread"] == 1  # A marking "all" never touched B's
