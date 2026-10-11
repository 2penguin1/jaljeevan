import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

# Per-signal display helpers: the strongest quote, the most confident place, the highest-scoring zone.
_QUOTE = "(SELECT l.evidence FROM signal_labels l WHERE l.signal_id = s.id ORDER BY l.severity DESC, l.code LIMIT 1)"
_PLACE = ("(SELECT sl.mention_text FROM signal_locations sl WHERE sl.signal_id = s.id "
          "ORDER BY sl.geo_confidence DESC LIMIT 1)")
_ZONE = ("(SELECT zs.zone_id FROM zone_signals zs JOIN zones z ON z.id = zs.zone_id WHERE zs.signal_id = s.id "
         "AND z.status NOT IN ('dismissed', 'resolved') ORDER BY z.score DESC LIMIT 1)")
_ZONE_FIELDS = """z.id, z.name, z.hazard, z.zone_type, z.status, z.score, z.trend, z.independent_sources,
                  z.population_est, z.population_urban, z.population_source, z.last_seen, z.district_id, z.area_id"""


class ReadRepository:
    """Read-only queries behind the public feed, zone pages, stats and ops pages."""

    def __init__(self, session: Session):
        self.session = session

    def _rows(self, sql: str, params: dict | None = None) -> list[dict]:
        return [dict(r) for r in self.session.execute(text(sql), params or {}).mappings()]

    def feed(self, before: tuple[datetime, uuid.UUID] | None, limit: int) -> list[dict]:
        """Keyset page: newest published first, id breaks ties so rows sharing a timestamp are never skipped."""
        at, after_id = before if before else (None, None)
        return self._rows(f"""
            SELECT s.id, s.title, s.english_summary, {_QUOTE} AS quote, {_PLACE} AS place, s.source, s.domain,
                   s.credibility, s.max_severity AS severity, s.hazards, s.published_at, s.url,
                   COALESCE(s.published_at, s.created_at) AS sort_at, {_ZONE} AS zone_id
            FROM signals s
            WHERE s.status = 'classified' AND s.relevant
              AND (CAST(:at AS timestamptz) IS NULL
                   OR (COALESCE(s.published_at, s.created_at), s.id) < (CAST(:at AS timestamptz), CAST(:id AS uuid)))
            ORDER BY sort_at DESC, s.id DESC LIMIT :lim""", {"at": at, "id": after_id, "lim": limit})

    def zones(self, hazard: str | None, status: str | None) -> list[dict]:
        return self._rows(f"""
            SELECT {_ZONE_FIELDS} FROM zones z
            WHERE (CAST(:hz AS text) IS NULL OR z.hazard = :hz) AND (CAST(:st AS text) IS NULL OR z.status = :st)
              AND z.status NOT IN ('dismissed', 'resolved')
            ORDER BY z.score DESC""", {"hz": hazard, "st": status})

    def zone(self, zone_id: uuid.UUID) -> dict | None:
        rows = self._rows(f"""
            SELECT {_ZONE_FIELDS}, ST_AsGeoJSON(ST_SimplifyPreserveTopology(z.geom, 0.001), 5) AS geometry,
                   ROUND(ST_X(z.centroid)::numeric, 4)::float AS lon, ROUND(ST_Y(z.centroid)::numeric, 4)::float AS lat,
                   d.name AS district
            FROM zones z LEFT JOIN admin_areas d ON d.id = z.district_id WHERE z.id = :id""", {"id": zone_id})
        return rows[0] if rows else None

    def zone_evidence(self, zone_id: uuid.UUID, limit: int | None = None) -> list[dict]:
        return self._rows(f"""
            SELECT s.id AS signal_id, {_QUOTE} AS quote, s.english_summary AS summary, s.title, s.source, s.domain,
                   s.credibility, zs.weight, s.max_severity AS severity, s.url, s.published_at, {_PLACE} AS place
            FROM zone_signals zs JOIN signals s ON s.id = zs.signal_id
            WHERE zs.zone_id = :id ORDER BY zs.weight DESC
            {"LIMIT :lim" if limit else ""}""", {"id": zone_id, "lim": limit})

    def zone_trend(self, zone_id: uuid.UUID, limit: int = 200) -> list[dict]:
        return self._rows("""
            SELECT at, score FROM (SELECT at, score FROM zone_snapshots WHERE zone_id = :id
                                   ORDER BY at DESC LIMIT :lim) recent ORDER BY at""", {"id": zone_id, "lim": limit})

    def overview(self, since: datetime) -> dict:
        return self._rows("""
            SELECT (SELECT COUNT(*) FROM zones WHERE status IN ('active', 'approved')) AS active_zones,
                   (SELECT COUNT(*) FROM zones WHERE status = 'watch') AS watch_zones,
                   (SELECT COUNT(*) FROM signals WHERE status <> 'pending' AND created_at >= :since)
                       AS posts_analysed_7d,
                   (SELECT COALESCE(SUM(population_est), 0) FROM zones WHERE status IN ('active', 'approved'))
                       AS people_affected,
                   (SELECT COUNT(DISTINCT COALESCE(domain, source)) FROM signals
                     WHERE status = 'classified' AND relevant AND created_at >= :since) AS sources""",
                          {"since": since})[0]

    def totals(self) -> dict:
        counts = self._rows("""SELECT COUNT(*) AS signals, COUNT(*) FILTER (WHERE status = 'classified') AS classified
                               FROM signals""")[0]
        rejected = self._rows("""SELECT rejected_reason AS reason, COUNT(*) AS n FROM signals
                                 WHERE status = 'rejected' GROUP BY rejected_reason ORDER BY n DESC""")
        tokens = self._rows("""
            SELECT COALESCE(SUM((stats->'classify'->>'input_tokens')::bigint), 0) AS input_tokens,
                   COALESCE(SUM((stats->'classify'->>'output_tokens')::bigint), 0) AS output_tokens
            FROM pipeline_runs""")[0]
        providers = self._rows("""
            SELECT p.key AS provider, SUM(p.value::bigint) AS batches
            FROM pipeline_runs r, jsonb_each_text(r.stats->'classify'->'providers') p
            WHERE jsonb_typeof(r.stats->'classify'->'providers') = 'object' GROUP BY p.key""")
        return {**counts, "rejected_by_reason": {r["reason"] or "unknown": r["n"] for r in rejected},
                "tokens": tokens, "batches_by_provider": {p["provider"]: p["batches"] for p in providers}}
