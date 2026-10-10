import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, text, true

from app.domain.scoring import EvidenceSignal
from app.domain.zones import Cluster, ClusterPoint
from app.models import AdminArea, Reaction, Signal, Zone, ZoneSignal, ZoneSnapshot
from app.repositories.base import BaseRepository

# Signals allowed to shape zones (spec): current, relevant, severe enough, recent, located, not near-duplicate,
# not flagged false/irrelevant by a reviewer.
_ELIGIBLE = """s.status = 'classified' AND s.relevant AND s.event_period = 'current'
  AND :hz = ANY(s.hazards) AND s.dup_of IS NULL AND s.max_severity >= 3
  AND COALESCE(s.published_at, s.created_at) >= :since
  AND NOT sl.ambiguous AND sl.geom IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM signal_feedback f WHERE f.signal_id = s.id AND f.verdict IN ('false','irrelevant'))"""


class ZoneRepository(BaseRepository[Zone]):
    model = Zone

    # -- concurrency -------------------------------------------------------------------------------
    def try_lock(self, hazard: str) -> bool:
        """Transaction-scoped advisory lock so overlapping runs never process the same hazard twice."""
        return bool(self.session.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"),
                                        {"k": f"zones:{hazard}"}))

    # -- evidence queries ------------------------------------------------------------------------
    def clusters(self, hazard: str, since: datetime, buffer_m: dict[str, int]) -> list[Cluster]:
        """Fine-grained clusters: points buffered by precision; intersecting buffers form one cluster."""
        # DDL cannot take bind parameters: create the temp table first, then fill it with INSERT ... SELECT.
        self.session.execute(text("DROP TABLE IF EXISTS zone_pts"))
        self.session.execute(text("""CREATE TEMP TABLE zone_pts (cid int, signal_id uuid, precision varchar,
                                     geo_confidence float, admin_area_id int, mention_text varchar, buf geometry)"""))
        self.session.execute(text(f"""
            INSERT INTO zone_pts
            SELECT ST_ClusterDBSCAN(buf, eps := 0, minpoints := 1) OVER () AS cid,
                   signal_id, precision, geo_confidence, admin_area_id, mention_text, buf
            FROM (SELECT sl.signal_id, sl.precision, sl.geo_confidence, sl.admin_area_id, sl.mention_text,
                         ST_Buffer(sl.geom::geography, CASE sl.precision WHEN 'ward' THEN :w
                                   WHEN 'village' THEN :v ELSE :t END)::geometry AS buf
                  FROM signal_locations sl JOIN signals s ON s.id = sl.signal_id
                  WHERE {_ELIGIBLE} AND sl.precision IN ('ward','village','town')) pts"""),
            {"hz": hazard, "since": since, "w": buffer_m["ward"], "v": buffer_m["village"], "t": buffer_m["town"]})
        shapes = self.session.execute(text("""
            SELECT cid, ST_AsEWKT(ST_ConvexHull(ST_Collect(buf))) AS hull,
                   ST_AsEWKT(ST_Centroid(ST_Collect(buf))) AS centroid
            FROM zone_pts GROUP BY cid ORDER BY cid""")).all()
        points = self.session.execute(text("""
            SELECT p.cid, p.signal_id, p.precision, p.geo_confidence, p.admin_area_id, p.mention_text,
                   COALESCE(a.level, p.precision) AS level, COALESCE(a.is_urban, false) AS is_urban
            FROM zone_pts p LEFT JOIN admin_areas a ON a.id = p.admin_area_id""")).all()
        by_cid: dict[int, list[ClusterPoint]] = {}
        for p in points:
            by_cid.setdefault(p.cid, []).append(ClusterPoint(p.signal_id, p.precision, p.geo_confidence,
                                                             p.admin_area_id, p.mention_text, p.level, p.is_urban))
        return [Cluster(s.hull, s.centroid, by_cid.get(s.cid, [])) for s in shapes]

    def district_evidence(self, hazard: str, since: datetime) -> dict[int, dict[uuid.UUID, float]]:
        rows = self.session.execute(text(f"""
            SELECT sl.admin_area_id AS district_id, sl.signal_id, MAX(sl.geo_confidence) AS conf
            FROM signal_locations sl JOIN signals s ON s.id = sl.signal_id
            WHERE {_ELIGIBLE} AND sl.precision = 'district' AND sl.admin_area_id IS NOT NULL
            GROUP BY sl.admin_area_id, sl.signal_id"""), {"hz": hazard, "since": since}).all()
        out: dict[int, dict[uuid.UUID, float]] = {}
        for r in rows:
            out.setdefault(r.district_id, {})[r.signal_id] = r.conf
        return out

    def evidence(self, confidence: dict[uuid.UUID, float]) -> list[tuple[uuid.UUID, EvidenceSignal, int | None]]:
        """(signal id, scoring evidence, people-affected hint). Corroborated = a 'same here' from another user."""
        if not confidence:
            return []
        ids = list(confidence)
        signals = self.session.scalars(select(Signal).where(Signal.id.in_(ids))).all()
        corroborated = set(self.session.scalars(text("""
            SELECT r.signal_id FROM reactions r JOIN signals s ON s.id = r.signal_id
            WHERE r.kind = 'same_here' AND r.signal_id = ANY(:ids)
              AND (s.author_user_id IS NULL OR r.user_id <> s.author_user_id)"""), {"ids": ids}))
        return [(s.id, EvidenceSignal(source=s.source, domain=s.domain, author=s.author,
                                      credibility=s.credibility if s.credibility is not None else 0.6,
                                      severity=s.max_severity or 1, published_at=s.published_at,
                                      geo_confidence=confidence[s.id], corroborated=s.id in corroborated),
                 s.people_affected_hint) for s in signals]

    def water_arrived(self, signal_ids, since: datetime) -> bool:
        ids = list(signal_ids)
        if not ids:
            return False
        return bool(self.session.scalar(select(func.count()).select_from(Reaction).where(
            Reaction.signal_id.in_(ids), Reaction.kind == "water_arrived", Reaction.created_at >= since)))

    # -- zone identity ----------------------------------------------------------------------------
    def match_fine(self, hazard: str, hull_ewkt: str, taken: set, min_iou: float, max_dist_m: float) -> Zone | None:
        rows = self.session.execute(text("""
            WITH h AS (SELECT ST_GeomFromEWKT(:hull) AS g)
            SELECT z.id,
                   ST_Area(ST_Intersection(z.geom, h.g)::geography)
                     / NULLIF(ST_Area(ST_Union(z.geom, h.g)::geography), 0) AS iou,
                   ST_DistanceSphere(z.centroid, ST_Centroid(h.g)) AS dist
            FROM zones z, h
            WHERE z.hazard = :hz AND z.zone_type <> 'district_wide'
              AND (ST_Intersects(z.geom, h.g) OR ST_DWithin(z.centroid::geography, ST_Centroid(h.g)::geography, :d))
            ORDER BY iou DESC NULLS LAST, dist ASC"""), {"hull": hull_ewkt, "hz": hazard, "d": max_dist_m}).all()
        for r in rows:
            if r.id not in taken and ((r.iou or 0) >= min_iou or r.dist <= max_dist_m):
                return self.session.get(Zone, r.id)
        return None

    def district_zone(self, hazard: str, district_id: int) -> Zone | None:
        return self.session.scalar(select(Zone).where(Zone.hazard == hazard, Zone.zone_type == "district_wide",
                                                      Zone.district_id == district_id))

    def district_at(self, point_ewkt: str) -> tuple[int, str] | None:
        row = self.session.execute(text("""SELECT id, name FROM admin_areas WHERE level = 'district'
                                           AND ST_Intersects(geom, ST_GeomFromEWKT(:p)) LIMIT 1"""),
                                   {"p": point_ewkt}).first()
        return (row.id, row.name) if row else None

    def population_of(self, area_ids: set[int]) -> int:
        if not area_ids:
            return 0
        return int(self.session.scalar(select(func.coalesce(func.sum(AdminArea.population), 0))
                                       .where(AdminArea.id.in_(list(area_ids)))) or 0)

    @staticmethod
    def set_shape(zone: Zone, hull_ewkt: str, centroid_ewkt: str) -> None:
        zone.geom = func.ST_GeomFromEWKT(hull_ewkt)
        zone.centroid = func.ST_GeomFromEWKT(centroid_ewkt)

    @staticmethod
    def set_shape_from_district(zone: Zone, district_id: int) -> None:
        district_geom = select(AdminArea.geom).where(AdminArea.id == district_id).scalar_subquery()
        zone.geom = district_geom
        zone.centroid = func.ST_PointOnSurface(district_geom)

    # -- per-run bookkeeping ----------------------------------------------------------------------
    def replace_signals(self, zone_id: uuid.UUID, weights: dict[uuid.UUID, float]) -> None:
        self.session.execute(delete(ZoneSignal).where(ZoneSignal.zone_id == zone_id))
        self.session.add_all([ZoneSignal(zone_id=zone_id, signal_id=sid, weight=w) for sid, w in weights.items()])
        self.session.flush()

    def snapshot(self, zone_id: uuid.UUID, at: datetime, score: float, signal_count: int) -> None:
        self.session.add(ZoneSnapshot(zone_id=zone_id, at=at, score=score, signal_count=signal_count))
        self.session.flush()

    def average_score(self, zone_id: uuid.UUID, start: datetime, end: datetime) -> float | None:
        value = self.session.scalar(select(func.avg(ZoneSnapshot.score)).where(
            ZoneSnapshot.zone_id == zone_id, ZoneSnapshot.at > start, ZoneSnapshot.at <= end))
        return float(value) if value is not None else None

    def unseen(self, hazard: str, taken: set) -> list[Zone]:
        return list(self.session.scalars(select(Zone).where(
            Zone.hazard == hazard, Zone.id.notin_(taken) if taken else true(),
            Zone.status.notin_(("dismissed", "resolved")))))

    def count_status(self, status: str) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Zone).where(Zone.status == status)) or 0)
