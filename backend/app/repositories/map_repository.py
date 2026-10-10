import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

ZONE_TOLERANCE = 0.005      # degrees (~500 m): enough detail for a zone outline on the globe
DISTRICT_TOLERANCE = 0.01   # degrees (~1 km): keeps the all-India district layer small


class MapRepository:
    """Read-only GeoJSON queries for the public map. Geometry is simplified and rounded to 4 dp in SQL."""

    def __init__(self, session: Session):
        self.session = session

    def zones(self, hazard: str) -> list[dict]:
        rows = self.session.execute(text("""
            SELECT id, name, hazard, zone_type, status, score, trend, population_est, independent_sources,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, :tol), 4) AS geometry,
                   ST_X(centroid) AS lon, ST_Y(centroid) AS lat
            FROM zones
            WHERE hazard = :hz AND status NOT IN ('dismissed', 'resolved') AND score > 0 AND geom IS NOT NULL
            ORDER BY score DESC"""), {"hz": hazard, "tol": ZONE_TOLERANCE}).mappings()
        return [dict(r) for r in rows]

    def districts(self) -> list[dict]:
        rows = self.session.execute(text("""
            SELECT id, name, state_code, ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, :tol), 4) AS geometry
            FROM admin_areas WHERE level = 'district' AND geom IS NOT NULL"""),
            {"tol": DISTRICT_TOLERANCE}).mappings()
        return [dict(r) for r in rows]

    def signals(self, hazard: str, since: datetime, limit: int = 1000) -> list[dict]:
        """One point per signal (its most confident location), newest first."""
        rows = self.session.execute(text("""
            SELECT * FROM (
              SELECT DISTINCT ON (s.id)
                     s.id, s.max_severity AS severity, s.source, s.title,
                     COALESCE(s.published_at, s.created_at) AS published_at,
                     ROUND(ST_X(sl.geom)::numeric, 4)::float AS lon, ROUND(ST_Y(sl.geom)::numeric, 4)::float AS lat,
                     (SELECT zs.zone_id FROM zone_signals zs WHERE zs.signal_id = s.id LIMIT 1) AS zone_id
              FROM signals s JOIN signal_locations sl ON sl.signal_id = s.id
              WHERE s.status = 'classified' AND s.relevant AND :hz = ANY(s.hazards) AND sl.geom IS NOT NULL
                AND NOT sl.ambiguous AND COALESCE(s.published_at, s.created_at) >= :since
              ORDER BY s.id, sl.geo_confidence DESC) one_per_signal
            ORDER BY published_at DESC
            LIMIT :lim"""), {"hz": hazard, "since": since, "lim": limit}).mappings()
        return [dict(r) for r in rows]

    @staticmethod
    def geometry(value: str | None) -> dict | None:
        return json.loads(value) if value else None
