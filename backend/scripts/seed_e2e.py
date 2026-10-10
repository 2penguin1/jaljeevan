"""Deterministic fixture for the frontend end-to-end tests, in its own database (jal_e2e).

Run: cd backend && uv run python -m scripts.seed_e2e
Creates the database if needed, empties it, and loads three zones (one per hazard), their posts and history.
Never point this at a database whose name does not end in "_e2e": it deletes every row.
"""
import os
from datetime import datetime, timedelta, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import Base, init_db
from app.models import (AdminArea, DistrictIndicator, PipelineRun, Signal, SignalLabel, SignalLocation, Zone,
                        ZoneSignal, ZoneSnapshot)

URL = os.environ.get("E2E_DATABASE_URL", "postgresql+psycopg://jal:jal@localhost:5433/jal_e2e")
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def ensure_database(url: str) -> None:
    name = url.rsplit("/", 1)[1]
    assert name.endswith("_e2e"), f"refusing to seed {name}: e2e databases must end in _e2e"
    admin = create_engine(url.rsplit("/", 1)[0] + "/jal", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}):
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()


def wipe(engine) -> None:
    with engine.begin() as conn:
        tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


ZONES = [
    # name, hazard, type, status, score, centroid, district (name, state, bbox), posts
    ("Mohol, Solapur", "drought", "rural", "active", 78.0, (75.65, 17.81), ("Solapur", "MH", (75.2, 17.3, 76.4, 18.4)), [
        ("thehindu.com", "rss", "Mohol villages wait 9 days for tankers", "No tanker has come for nine days in Mohol",
         "No tanker has come for nine days", "Mohol", 4, 0.8),
        ("timesofindia.indiatimes.com", "rss", "Solapur borewells run dry", "Borewells in Mohol taluka have run dry",
         "Borewells in Mohol taluka have run dry", "Mohol", 4, 0.8),
        ("reddit.com", "reddit", "<b>Our taps are dry</b> in Mohol", "Our taps are dry since last week, buying cans",
         "Our taps are dry since last week", "Mohol", 3, 0.4),
    ]),
    ("Patna district", "flood", "district_wide", "active", 66.0, (85.14, 25.6), ("Patna", "BR", (84.7, 25.2, 85.9, 25.9)), [
        ("indianexpress.com", "rss", "Ganga crosses danger mark at Patna", "The Ganga crossed the danger mark at Gandhi Ghat",
         "The Ganga crossed the danger mark", "Patna", 4, 0.8),
        ("x.com", "x", "", "Water entered houses in Danapur, families moving to roofs", "Water entered houses in Danapur",
         "Danapur", 4, 0.4),
    ]),
    ("Jaipur", "heat", "town", "watch", 31.0, (75.79, 26.91), ("Jaipur", "RJ", (75.3, 26.5, 76.3, 27.3)), [
        ("x.com", "x", "", "Jaipur hit 46 degrees today, two labourers fainted at the site", "two labourers fainted",
         "Jaipur", 3, 0.4),
    ]),
]


def seed(session: Session) -> None:
    n = 0
    for zi, (name, hazard, ztype, status, score, (lon, lat), (dname, state, bbox), posts) in enumerate(ZONES):
        district = AdminArea(level="district", name=dname, name_norm=dname.lower(), state_code=state,
                             geom=from_shape(box(*bbox), srid=4326), population=4_000_000)
        session.add(district)
        session.flush()
        if hazard == "drought":
            session.add(DistrictIndicator(district_id=district.id, period=NOW.date(), rainfall_departure_pct=-48,
                                          source="imd"))
        zone = Zone(name=name, hazard=hazard, zone_type=ztype, status=status, score=score, trend="escalating",
                    independent_sources=len({p[0] for p in posts}), population_est=120_000 if ztype != "district_wide"
                    else 5_838_465, district_id=district.id, first_seen=NOW - timedelta(days=3), last_seen=NOW,
                    geom=from_shape(Point(lon, lat).buffer(0.12 if ztype != "district_wide" else 0.4), srid=4326),
                    centroid=from_shape(Point(lon, lat), srid=4326))
        session.add(zone)
        session.flush()
        weights = []
        for pi, (domain, source, title, body, quote, place, severity, cred) in enumerate(posts):
            n += 1
            published = NOW - timedelta(hours=2 + zi * 5 + pi * 3)
            sig = Signal(source=source, url=f"https://{domain}/e2e/{n}", domain=domain, title=title, text=body,
                         content_hash=f"e2e-{n}", simhash=n, status="classified", relevant=True,
                         event_period="current", hazards=[hazard], max_severity=severity, credibility=cred,
                         english_summary=body, published_at=published, created_at=published)
            session.add(sig)
            session.flush()
            session.add(SignalLabel(signal_id=sig.id, code=f"{hazard.upper()}_E2E", l1_code=hazard.upper(),
                                    severity=severity, evidence=quote))
            session.add(SignalLocation(signal_id=sig.id, mention_text=place, precision="town", geo_confidence=0.9,
                                       geom=from_shape(Point(lon + pi * 0.03, lat + pi * 0.02), srid=4326)))
            weight = round(cred * severity / 5, 3)
            weights.append(weight)
            session.add(ZoneSignal(zone_id=zone.id, signal_id=sig.id, weight=weight))
        for day, s in enumerate([score - 18, score - 9, score]):
            session.add(ZoneSnapshot(zone_id=zone.id, at=NOW - timedelta(days=2 - day), score=s, signal_count=len(posts)))
    session.add(Signal(source="rss", url="https://example.com/e2e/rejected", title="Cricket final tonight", text="",
                       content_hash="e2e-rejected", simhash=0, status="rejected", rejected_reason="no_keyword",
                       created_at=NOW))
    session.add(PipelineRun(kind="local", started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=3),
                            stats={"ingest": {"rss": {"fetched": 40, "inserted": 6}, "x": {"error": "x: HTTP 429"}},
                                   "classify": {"classified": 6, "input_tokens": 9000, "output_tokens": 2100,
                                                "providers": {"bedrock:apac.amazon.nova-lite-v1:0": 1}},
                                   "zones": {"active": 2}}))


def main() -> None:
    ensure_database(URL)
    engine = create_engine(URL)
    init_db(engine)
    wipe(engine)
    with Session(engine) as session:
        seed(session)
        session.commit()
    engine.dispose()
    print(f"seeded e2e fixture into {URL.rsplit('/', 1)[1]}")


if __name__ == "__main__":
    main()
