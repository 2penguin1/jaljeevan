import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal, session_scope
from app.models import SourceDomain


def _cleanup():
    with SessionLocal() as s:
        s.execute(delete(SourceDomain).where(SourceDomain.domain.like("scope-test%")))
        s.commit()


def test_session_scope_commits_on_success():
    _cleanup()
    with session_scope() as s:
        s.add(SourceDomain(domain="scope-test-ok", tier="regional", credibility=0.7))
    with SessionLocal() as s:
        assert s.scalar(select(SourceDomain).where(SourceDomain.domain == "scope-test-ok")) is not None
    _cleanup()


def test_session_scope_rolls_back_on_error():
    _cleanup()
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            s.add(SourceDomain(domain="scope-test-fail", tier="regional", credibility=0.7))
            s.flush()
            raise RuntimeError("boom")
    with SessionLocal() as s:
        assert s.scalar(select(SourceDomain).where(SourceDomain.domain == "scope-test-fail")) is None
