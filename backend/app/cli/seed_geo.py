"""Load reference geography into the database.

Usage (from backend/):  uv run python -m app.cli.seed_geo [--ward-name-prop NAME]
Data files live in app/data/seed/ (see its README.md for sources).
"""
import argparse
from pathlib import Path

from app.core.database import init_db, session_scope
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.source_domain_repository import SourceDomainRepository
from app.services.geo_seed_service import GeoSeedService

DATA = Path(__file__).resolve().parents[1] / "data" / "seed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ward-name-prop", default="KGISWardName", help="ward-name property in the BBMP GeoJSON")
    parser.add_argument("--bengaluru-population", type=int, default=13_600_000)
    args = parser.parse_args()

    init_db()
    with session_scope() as session:
        areas = AdminAreaRepository(session)
        svc = GeoSeedService(areas, IndicatorRepository(session), SourceDomainRepository(session))
        if areas.has_any():
            print("admin_areas already loaded - skipping geography")
        else:
            pop_csv = DATA / "district_population.csv"
            print("districts:", svc.load_districts(DATA / "india_district.geojson",
                                                   population_csv=pop_csv if pop_csv.exists() else None))
            print("places:", svc.load_geonames(DATA / "IN.txt", DATA / "admin1CodesASCII.txt"))
            wards = DATA / "bbmp_wards.geojson"
            if wards.exists():
                print("wards:", svc.load_wards(wards, args.ward_name_prop, args.bengaluru_population,
                                               "KA", "Bangalore Urban"))
            svc.link_parents()
        imd = DATA / "imd_rainfall_2026.csv"
        if imd.exists():
            print("indicators:", svc.load_indicators(imd))
        print("source domains:", svc.seed_source_domains())


if __name__ == "__main__":
    main()
