import json

from sqlalchemy import func, select

from app.models import AdminArea, DistrictIndicator, SourceDomain
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.source_domain_repository import SourceDomainRepository
from app.services.geo_seed_service import GeoSeedService

SQUARE = {"type": "Polygon", "coordinates": [[[71, 25], [72, 25], [72, 26], [71, 26], [71, 25]]]}


def service(db) -> GeoSeedService:
    return GeoSeedService(AdminAreaRepository(db), IndicatorRepository(db), SourceDomainRepository(db))


def district_file(tmp_path):
    gj = tmp_path / "d.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"NAME_1": "Rajasthan", "NAME_2": "Barmer"}, "geometry": SQUARE}]}))
    return gj


def test_districts_towns_villages_wards_and_parent_link(db, tmp_path):
    svc = service(db)
    pop = tmp_path / "pop.csv"
    pop.write_text("state,district,population\nRajasthan,Barmer,2603751\n")
    assert svc.load_districts(district_file(tmp_path), population_csv=pop) == 1

    admin1 = tmp_path / "admin1.txt"
    admin1.write_text("IN.24\tRajasthan\tRajasthan\t1258899\n")
    places = tmp_path / "IN.txt"
    rows = [
        ["1", "Barmer", "Barmer", "", "25.75", "71.39", "P", "PPLA2", "IN", "", "24", "", "", "", "100000"],
        ["2", "Dhorimanna", "Dhorimanna", "", "25.20", "71.43", "P", "PPL", "IN", "", "24", "", "", "", "0"],
        ["3", "Station Road", "Station Road", "", "25.74", "71.38", "P", "PPLX", "IN", "", "24", "", "", "", "0"],
        ["4", "Some Hill", "Some Hill", "", "25.5", "71.5", "T", "HLL", "IN", "", "24", "", "", "", "0"],
    ]
    places.write_text("\n".join("\t".join(r + ["", "", "Asia/Kolkata", "2024-01-01"]) for r in rows) + "\n")
    assert svc.load_geonames(places, admin1) == 3  # the hill (feature class T) is skipped
    svc.link_parents()

    town = db.scalar(select(AdminArea).where(AdminArea.name == "Barmer", AdminArea.level == "town"))
    district = db.scalar(select(AdminArea).where(AdminArea.level == "district"))
    assert town.state_code == "RJ" and town.is_urban is True
    assert town.parent_id == district.id and town.district_name == "Barmer"
    assert district.population == 2603751
    village = db.scalar(select(AdminArea).where(AdminArea.name == "Dhorimanna"))
    assert village.level == "village" and village.parent_id == district.id
    neighbourhood = db.scalar(select(AdminArea).where(AdminArea.name == "Station Road"))
    assert neighbourhood.level == "ward" and neighbourhood.is_urban is True


def test_wards_split_city_population(db, tmp_path):
    gj = tmp_path / "w.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"WARD_NAME": f"W{i}"}, "geometry": SQUARE} for i in range(4)]}))
    assert service(db).load_wards(gj, "WARD_NAME", 400_000, "KA", "Bangalore Urban") == 4
    assert db.scalar(select(AdminArea.population).where(AdminArea.name == "W0")) == 100_000


def test_indicators_and_source_domains(db, tmp_path):
    svc = service(db)
    svc.load_districts(district_file(tmp_path))
    csv = tmp_path / "imd.csv"
    csv.write_text("state_code,district,period,rainfall_departure_pct\nRJ,Barmer,2026-09-30,-52\nRJ,Nowhere,2026-09-30,-10\n")
    assert svc.load_indicators(csv) == 1  # unknown district skipped
    ind = db.scalar(select(DistrictIndicator))
    assert ind.rainfall_departure_pct == -52 and ind.source == "imd"
    assert svc.seed_source_domains() == 36
    assert svc.seed_source_domains() == 36  # idempotent
    assert db.scalar(select(func.count()).select_from(SourceDomain)) == 36
    assert SourceDomainRepository(db).credibility("pib.gov.in") == 1.0
