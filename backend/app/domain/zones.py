"""Pure zone rules and value objects used by zone detection."""
import uuid
from dataclasses import dataclass, field


class ZoneTypeClassifier:
    """urban_pocket (ward, urban locality, or a neighbourhood inside a million-plus city's district) /
    town (whole-town mention) / rural. District zones are set elsewhere."""

    def classify(self, locations: list[dict]) -> str:
        if any(loc["level"] == "ward" or (loc["is_urban"] and loc["precision"] != "town")
               or (loc.get("district_urban") and loc["precision"] in ("ward", "village")) for loc in locations):
            return "urban_pocket"
        if any(loc["precision"] == "town" for loc in locations):
            return "town"
        return "rural"


@dataclass(frozen=True)
class ClusterPoint:
    signal_id: uuid.UUID
    precision: str
    geo_confidence: float
    admin_area_id: int | None
    mention_text: str
    level: str
    is_urban: bool
    district_urban: bool = False  # the point's district holds a 1M+ city


@dataclass(frozen=True)
class Cluster:
    hull_ewkt: str
    centroid_ewkt: str
    points: list[ClusterPoint] = field(default_factory=list)

    def confidence_by_signal(self) -> dict[uuid.UUID, float]:
        """Best geo-confidence per signal (a signal can contribute several locations to one cluster)."""
        best: dict[uuid.UUID, float] = {}
        for p in self.points:
            best[p.signal_id] = max(best.get(p.signal_id, 0.0), p.geo_confidence)
        return best
