"""Seed the relief-tender demo: one government office, its officer, and demo tanker vendors near drought areas.

Usage (from backend/): uv run python -m app.cli.seed_crm      (safe to run again: existing names are skipped)
Every vendor is marked is_demo and named "(demo)": they are not real businesses.
"""
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.core.database import init_db, session_scope
from app.models import Organization, User

GOVERNMENT = "Relief & Rehabilitation Department, Maharashtra"
# name, state, lon, lat, tankers, Rs/kL, reliability
VENDORS = [
    ("Solapur Jal Tankers (demo)", "MH", 75.91, 17.66, 18, 58, 0.92),
    ("Akkalkot Water Carriers (demo)", "MH", 76.21, 17.53, 9, 62, 0.88),
    ("Pandharpur Supply Co. (demo)", "MH", 75.33, 17.68, 14, 55, 0.85),
    ("Beed Tanker Services (demo)", "MH", 75.76, 18.99, 22, 60, 0.90),
    ("Latur Neer Logistics (demo)", "MH", 76.56, 18.40, 16, 57, 0.94),
    ("Dharashiv Water Movers (demo)", "MH", 76.04, 18.18, 11, 64, 0.81),
    ("Jalna Tanker Union (demo)", "MH", 75.88, 19.84, 20, 59, 0.87),
    ("Sambhajinagar Aqua Fleet (demo)", "MH", 75.34, 19.88, 30, 66, 0.95),
    ("Ahilyanagar Jaldhara (demo)", "MH", 74.74, 19.10, 15, 61, 0.83),
    ("Nanded Water Wheels (demo)", "MH", 77.32, 19.15, 12, 63, 0.86),
    ("Vijayapura Neeru Sarabaraju (demo)", "KA", 75.71, 16.83, 17, 54, 0.89),
    ("Kalaburagi Tanker Seva (demo)", "KA", 76.83, 17.33, 21, 56, 0.91),
    ("Gadag Water Supply (demo)", "KA", 75.63, 15.43, 10, 65, 0.84),
    ("Belagavi Jal Fleet (demo)", "KA", 74.50, 15.85, 25, 60, 0.93),
    ("Ballari Tankers (demo)", "KA", 76.92, 15.14, 13, 58, 0.80),
    ("Raichur Water Movers (demo)", "KA", 77.36, 16.20, 8, 67, 0.78),
]


def main() -> None:
    init_db()
    with session_scope() as s:
        names = set(s.scalars(select(Organization.name)))
        if GOVERNMENT not in names:
            gov = Organization(kind="government", name=GOVERNMENT, state_code="MH", is_demo=True)
            s.add(gov)
            s.flush()
            s.add(User(email="officer@relief.demo", password_hash="!", name="Demo relief officer", role="gov_admin",
                       org_id=gov.id))
        added = 0
        for name, state, lon, lat, tankers, price, reliability in VENDORS:
            if name in names:
                continue
            s.add(Organization(kind="vendor", name=name, state_code=state, geom=from_shape(Point(lon, lat), srid=4326),
                               tanker_count=tankers, tanker_capacity_kl=10, base_price_per_kl=price,
                               reliability=reliability, is_demo=True))
            added += 1
    print(f"government office ready; {added} demo vendors added")


if __name__ == "__main__":
    main()
