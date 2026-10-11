import time
import uuid

import pytest

from app.core.security import (InvalidToken, LoginBrake, hash_password, issue_token, read_token, verify_password)


def test_passwords_are_hashed_and_checked():
    hashed = hash_password("s3cret-pass")
    assert hashed != "s3cret-pass" and hashed.startswith("$2")
    assert verify_password("s3cret-pass", hashed) and not verify_password("wrong", hashed)
    assert not verify_password("anything", "!")  # seeded accounts without a password can never log in


def test_tokens_carry_the_user_and_expire():
    uid, org = uuid.uuid4(), uuid.uuid4()
    claims = read_token(issue_token(uid, "vendor", org, key="k" * 32), key="k" * 32)
    assert claims.user_id == uid and claims.role == "vendor" and claims.org_id == org
    expired = issue_token(uid, "vendor", None, key="k" * 32, ttl_seconds=-1)
    with pytest.raises(InvalidToken):
        read_token(expired, key="k" * 32)
    with pytest.raises(InvalidToken):
        read_token(issue_token(uid, "vendor", None, key="k" * 32), key="another-key-" * 3)


def test_the_login_brake_stops_password_guessing():
    brake = LoginBrake(max_failures=3, window_seconds=60, clock=lambda: 1000.0)
    for _ in range(3):
        assert brake.allowed("a@b.c", "ip")
        brake.failed("a@b.c", "ip")
    assert not brake.allowed("a@b.c", "ip") and brake.allowed("other@b.c", "ip")
    later = LoginBrake(max_failures=3, window_seconds=60, clock=lambda: 1000.0 + 61)
    later._failures = brake._failures
    assert later.allowed("a@b.c", "ip")


def test_the_brake_counts_per_email_and_address_and_forgets_old_entries():
    brake = LoginBrake(max_failures=2, window_seconds=60, clock=lambda: 1000.0)
    for _ in range(2):
        brake.failed("officer@relief.demo", "1.1.1.1")
    assert not brake.allowed("officer@relief.demo", "1.1.1.1")
    assert brake.allowed("officer@relief.demo", "2.2.2.2")  # a stranger cannot lock the real officer out
    assert brake.allowed("nobody@x.y", "3.3.3.3") and len(brake._failures) == 1  # asking never stores anything


def test_a_server_never_signs_with_the_public_development_key(monkeypatch):
    from app.core import security
    monkeypatch.setattr(security.settings, "jwt_secret", None)
    monkeypatch.setattr(security.settings, "cookie_secure", False)
    monkeypatch.setattr(security.settings, "db_host", "db.abc.rds.amazonaws.com")  # running on AWS
    with pytest.raises(RuntimeError):
        security.signing_key()
