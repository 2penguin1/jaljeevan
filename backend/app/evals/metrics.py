from app.domain.geo import haversine_km


class EvalScorer:
    """Compares hand-labelled expectations with classifier output. Pairs are (expected, predicted) dicts."""

    TARGETS = {"relevance_precision": 0.85, "period_accuracy": 0.9}
    GEO_TOLERANCE_KM = 10

    @staticmethod
    def _ratio(num: float, den: float) -> float | None:
        return num / den if den else None

    def score(self, pairs) -> dict:
        tp = fp = fn = 0
        period_ok = period_n = 0
        l1_tp = l1_fp = l1_fn = 0
        severity_errors: list[int] = []
        geo_ok = geo_n = 0
        for expected, predicted in pairs:
            exp_rel, pred_rel = bool(expected["relevant"]), bool(predicted["relevant"])
            tp += exp_rel and pred_rel
            fp += (not exp_rel) and pred_rel
            fn += exp_rel and not pred_rel
            if exp_rel and pred_rel:
                period_n += 1
                period_ok += expected["event_period"] == predicted["event_period"]
                if expected.get("severity") is not None and predicted.get("severity") is not None:
                    severity_errors.append(abs(expected["severity"] - predicted["severity"]))
                coords = (expected.get("lon"), expected.get("lat"), predicted.get("lon"), predicted.get("lat"))
                if None not in coords:
                    geo_n += 1
                    geo_ok += haversine_km(coords[:2], coords[2:]) <= self.GEO_TOLERANCE_KM
            exp_l1, pred_l1 = set(expected.get("l1") or []), set(predicted.get("l1") or [])
            l1_tp += len(exp_l1 & pred_l1)
            l1_fp += len(pred_l1 - exp_l1)
            l1_fn += len(exp_l1 - pred_l1)
        precision, recall = self._ratio(l1_tp, l1_tp + l1_fp), self._ratio(l1_tp, l1_tp + l1_fn)
        return {
            "n": len(pairs),
            "relevance_precision": self._ratio(tp, tp + fp),
            "relevance_recall": self._ratio(tp, tp + fn),
            "period_accuracy": self._ratio(period_ok, period_n),
            "l1_f1": (2 * precision * recall / (precision + recall)) if precision and recall else 0.0,
            "severity_mae": (sum(severity_errors) / len(severity_errors)) if severity_errors else None,
            "geo_within_10km": self._ratio(geo_ok, geo_n),
        }

    def failed_targets(self, metrics: dict) -> list[str]:
        return [name for name, target in self.TARGETS.items() if (metrics.get(name) or 0) < target]
