import pytest

from app.evals.metrics import EvalScorer


def test_metrics():
    pairs = [
        ({"relevant": True, "event_period": "current", "l1": ["SUPPLY"], "severity": 4, "lat": 12.99, "lon": 77.69},
         {"relevant": True, "event_period": "current", "l1": ["SUPPLY", "RELIEF"], "severity": 3,
          "lat": 12.995, "lon": 77.70}),
        ({"relevant": True, "event_period": "past", "l1": ["FLOOD"], "severity": 5, "lat": 19.07, "lon": 72.87},
         {"relevant": True, "event_period": "current", "l1": ["FLOOD"], "severity": 5, "lat": 28.6, "lon": 77.2}),
        ({"relevant": False, "event_period": None, "l1": [], "severity": None, "lat": None, "lon": None},
         {"relevant": True, "event_period": "current", "l1": ["SUPPLY"], "severity": 2, "lat": None, "lon": None}),
        ({"relevant": True, "event_period": "current", "l1": ["HEAT"], "severity": 3, "lat": None, "lon": None},
         {"relevant": False, "event_period": None, "l1": [], "severity": None, "lat": None, "lon": None}),
    ]
    m = EvalScorer().score(pairs)
    assert m["n"] == 4
    assert m["relevance_precision"] == pytest.approx(2 / 3)
    assert m["relevance_recall"] == pytest.approx(2 / 3)
    assert m["period_accuracy"] == pytest.approx(0.5)       # judged where both say relevant
    assert m["l1_f1"] == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))  # tp=2 fp=2 fn=1
    assert m["severity_mae"] == pytest.approx(0.5)          # |4-3| and |5-5|
    assert m["geo_within_10km"] == pytest.approx(0.5)       # 1 of 2 with both coordinates


def test_targets_gate():
    scorer = EvalScorer()
    assert scorer.failed_targets({"relevance_precision": 0.9, "period_accuracy": 0.95}) == []
    assert scorer.failed_targets({"relevance_precision": 0.8, "period_accuracy": None}) == [
        "relevance_precision", "period_accuracy"]


def test_empty_set_is_safe():
    m = EvalScorer().score([])
    assert m["n"] == 0 and m["relevance_precision"] is None and m["l1_f1"] == 0.0
