from datetime import datetime, timedelta, timezone

import pytest

from app.domain.hazards import HazardPolicies
from app.domain.lifecycle import ZoneStateMachine
from app.domain.scoring import EvidenceSignal, ScoringConfig, ZoneScorer

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
scorer = ZoneScorer(ScoringConfig())
machine = ZoneStateMachine(ScoringConfig())
policies = HazardPolicies.default()


def ev(source="gdelt", domain="thehindu.com", author=None, cred=0.8, sev=5, age_days=0.0, conf=1.0,
       corroborated=False) -> EvidenceSignal:
    return EvidenceSignal(source=source, domain=domain, author=author, credibility=cred, severity=sev,
                          published_at=NOW - timedelta(days=age_days), geo_confidence=conf,
                          corroborated=corroborated)


def test_recency_half_lives():
    assert scorer.recency(NOW - timedelta(days=7), NOW, "reddit") == pytest.approx(0.5)
    assert scorer.recency(NOW - timedelta(days=14), NOW, "gdelt") == pytest.approx(0.5)
    assert scorer.recency(NOW + timedelta(hours=2), NOW, "x") == 1.0     # clock skew never boosts
    assert scorer.recency(None, NOW, "rss") == pytest.approx(0.5)        # unknown date = assume 14 days old


def test_weight_combines_factors_and_citizen_corroboration():
    assert scorer.weight(ev(), NOW) == pytest.approx(0.8)
    assert scorer.weight(ev(source="citizen", cred=0.5, corroborated=True), NOW) == pytest.approx(0.7)
    assert scorer.weight(ev(source="citizen", cred=0.5), NOW) == pytest.approx(0.5)
    assert scorer.weight(ev(cred=0.8, sev=3, conf=0.5), NOW) == pytest.approx(0.8 * 0.65 * 0.5)


def test_noisy_or_and_score():
    assert scorer.noisy_or([]) == 0.0
    assert scorer.noisy_or([0.5, 0.5]) == pytest.approx(0.75)
    assert scorer.score([0.5, 0.5]) == 75.0
    assert scorer.score([0.5], boost=0.4) == 70.0
    assert scorer.score([1.0, 1.0]) == 100.0


def test_independent_sources_collapse_same_outlet_and_author():
    evs = [ev(source="gdelt", domain="thehindu.com"), ev(source="rss", domain="www.thehindu.com"),
           ev(source="reddit", domain="reddit.com", author="u1"), ev(source="reddit", domain="reddit.com", author="u1"),
           ev(source="x", domain="x.com", author="u2")]
    assert scorer.independent_sources(evs) == 3


def test_evidence_rule():
    two = [ev(domain="a.com"), ev(domain="b.com")]
    assert scorer.evidence_ok(two, boost=0.0)
    assert scorer.evidence_ok([ev(cred=1.0)], boost=0.0)          # one official source
    assert scorer.evidence_ok([ev(cred=0.4)], boost=0.2)          # indicator support
    assert not scorer.evidence_ok([ev(cred=0.8)], boost=0.0)      # single unofficial source -> watch


def test_trend():
    assert scorer.trend(50, None, is_new=True) == "new"
    assert scorer.trend(70, 55, is_new=False) == "escalating"
    assert scorer.trend(40, 55, is_new=False) == "easing"
    assert scorer.trend(52, 55, is_new=False) == "stable"
    assert scorer.trend(52, None, is_new=False) == "stable"


def test_hazard_policies():
    assert policies.get("drought").boost({"rainfall_departure_pct": -52}) == 0.4
    assert policies.get("drought").boost({"rainfall_departure_pct": -25}) == 0.2
    assert policies.get("heat").boost({"apparent_tmax_c": 46, "tmax_c": 41}) == 0.4
    assert policies.get("heat").boost({"apparent_tmax_c": 42, "tmax_c": 40.5}) == 0.2
    assert policies.get("flood").boost({"precip_mm_24h": 120}) == 0.4
    assert policies.get("flood").boost({"precip_mm_24h": None}) == 0.0
    assert policies.get("drought").boost(None) == 0.0
    assert policies.get("drought").indicator_source == "imd" and policies.get("heat").indicator_source == "open-meteo"
    assert sorted(p.hazard for p in policies.all()) == ["drought", "flood", "heat", "water"]
    assert policies.get("water").boost({"precip_mm_24h": 500}) == 0.0 and policies.get("water").indicator_source is None
    assert {p.hazard: p.zoning for p in policies.all()}["water"] == "posts"


def test_state_machine_hysteresis():
    assert machine.next("watch", 65, True, None, NOW, False) == ("active", None)
    assert machine.next("active", 50, True, None, NOW, False)[0] == "active"          # between thresholds: hold
    assert machine.next("watch", 65, False, None, NOW, False)[0] == "watch"           # no evidence: watch
    assert machine.next("active", 30, True, None, NOW, True) == ("active", NOW)       # start the 72h clock
    assert machine.next("active", 30, True, NOW - timedelta(hours=73), NOW, True)[0] == "resolving"
    assert machine.next("active", 30, True, NOW - timedelta(hours=73), NOW, False)[0] == "active"
    assert machine.next("approved", 30, True, NOW - timedelta(hours=80), NOW, True)[0] == "resolving"
    assert machine.next("approved", 50, False, None, NOW, False)[0] == "approved"     # never demoted
    assert machine.next("dismissed", 99, True, None, NOW, False)[0] == "dismissed"
    assert machine.next("resolved", 70, True, None, NOW, False)[0] == "active"        # re-emerged
    assert machine.next("resolving", 70, True, NOW, NOW, False) == ("active", None)
