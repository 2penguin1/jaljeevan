"""Loads India's reference geography and source credibility into the database (run once via the CLI)."""
import csv
import json
from datetime import date
from pathlib import Path

from shapely.geometry import shape

from app.domain.states import StateCodes
from app.domain.text import TextFingerprinter
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.source_domain_repository import SourceDomainRepository

# Credibility tiers (spec: official 1.0, national 0.8, regional 0.7).
SOURCE_DOMAINS: dict[str, tuple[float, tuple[str, ...]]] = {
    "official": (1.0, ("pib.gov.in", "imd.gov.in", "mausam.imd.gov.in", "ndma.gov.in", "cgwb.gov.in",
                       "cwc.gov.in", "jalshakti-dowr.gov.in")),
    "national": (0.8, ("thehindu.com", "indianexpress.com", "hindustantimes.com", "timesofindia.indiatimes.com",
                       "ndtv.com", "indiatoday.in", "livemint.com", "scroll.in", "thewire.in", "downtoearth.org.in",
                       "newindianexpress.com", "business-standard.com", "theprint.in", "news18.com")),
    "regional": (0.7, ("deccanherald.com", "tribuneindia.com", "dtnext.in", "bangaloremirror.indiatimes.com",
                       "thehansindia.com", "telanganatoday.com", "lokmat.com", "bhaskar.com", "amarujala.com",
                       "jagran.com", "patrika.com", "onmanorama.com", "mathrubhumi.com", "dailypioneer.com",
                       "freepressjournal.in")),
}


class GeoSeedService:
    TOWN_POP = 20_000
    URBAN_POP = 100_000
    TOWN_CODES = frozenset({"PPLC", "PPLA", "PPLA2", "PPLA3"})
    NEIGHBOURHOOD_CODE = "PPLX"  # a named locality inside a city, e.g. Mahadevapura -> treated as a ward

    def __init__(self, areas: AdminAreaRepository, indicators: IndicatorRepository,
                 domains: SourceDomainRepository, fingerprinter: TextFingerprinter | None = None):
        self.areas = areas
        self.indicators = indicators
        self.domains = domains
        self.fp = fingerprinter or TextFingerprinter()

    def load_districts(self, geojson_path, state_prop: str = "NAME_1", district_prop: str = "NAME_2",
                       population_csv=None) -> int:
        populations = self._read_populations(population_csv) if population_csv else {}
        rows = []
        for feature in json.loads(Path(geojson_path).read_text(encoding="utf-8"))["features"]:
            props = feature["properties"]
            code, name = StateCodes.code(props.get(state_prop)), props.get(district_prop)
            if not code or not name:
                continue
            rows.append({"level": "district", "name": name, "name_norm": self.fp.norm_name(name),
                         "state_code": code, "district_name": name,
                         "population": populations.get((code, self.fp.norm_name(name))),
                         "wkt": shape(feature["geometry"]).wkt})
        return self.areas.bulk_insert(rows)

    def load_geonames(self, places_txt, admin1_txt) -> int:
        """GeoNames IN.txt: every populated place (feature class P) in India with coordinates and population."""
        admin1 = {}
        with open(admin1_txt, encoding="utf-8") as fh:
            for line in fh:
                code, name, *_ = line.rstrip("\n").split("\t")
                if code.startswith("IN."):
                    admin1[code[3:]] = StateCodes.code(name)
        rows = []
        with open(places_txt, encoding="utf-8") as fh:
            for line in fh:
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 15 or cols[6] != "P" or not admin1.get(cols[10]):
                    continue
                rows.append(self._place_row(cols, admin1[cols[10]]))
        return self.areas.bulk_insert(rows)

    def load_wards(self, geojson_path, name_prop: str, city_population: int, state_code: str,
                   district_name: str) -> int:
        features = json.loads(Path(geojson_path).read_text(encoding="utf-8"))["features"]
        per_ward = city_population // max(1, len(features))  # ponytail: even split; use ward census if found
        rows = [{"level": "ward", "name": str(f["properties"][name_prop]),
                 "name_norm": self.fp.norm_name(str(f["properties"][name_prop])), "state_code": state_code,
                 "district_name": district_name, "is_urban": True, "population": per_ward,
                 "wkt": shape(f["geometry"]).wkt} for f in features]
        return self.areas.bulk_insert(rows)

    def link_parents(self) -> None:
        self.areas.link_parents()

    def load_indicators(self, csv_path) -> int:
        count = 0
        with open(csv_path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                district_id = self.areas.find_district_id(r["state_code"], self.fp.norm_name(r["district"]))
                if district_id is None:
                    continue
                self.indicators.upsert(district_id, date.fromisoformat(r["period"]), "imd",
                                       rainfall_departure_pct=float(r["rainfall_departure_pct"]))
                count += 1
        return count

    def seed_source_domains(self) -> int:
        count = 0
        for tier, (credibility, domains) in SOURCE_DOMAINS.items():
            for domain in domains:
                self.domains.upsert(domain, tier, credibility)
                count += 1
        return count

    # -- helpers --------------------------------------------------------------------------------
    def _read_populations(self, path) -> dict[tuple[str, str], int]:
        with open(path, encoding="utf-8") as fh:
            return {(StateCodes.code(r["state"]), self.fp.norm_name(r["district"])): int(r["population"])
                    for r in csv.DictReader(fh)}

    MAX_ALIASES = 30

    def _aliases(self, alternate_names: str, name_norm: str) -> list[str]:
        """GeoNames alternate names (Gurugram, Bengaluru, Hindi script...), normalised, without the main name."""
        out: list[str] = []
        for raw in (alternate_names or "").split(","):
            alias = self.fp.norm_name(raw)
            if alias and alias != name_norm and alias not in out:
                out.append(alias)
        return out[:self.MAX_ALIASES]

    def _place_row(self, cols: list[str], state_code: str) -> dict:
        pop, feature_code = int(cols[14] or 0), cols[7]
        name_norm = self.fp.norm_name(cols[2] or cols[1])
        neighbourhood = feature_code == self.NEIGHBOURHOOD_CODE
        is_town = pop >= self.TOWN_POP or feature_code in self.TOWN_CODES
        return {"level": "ward" if neighbourhood else ("town" if is_town else "village"),
                "name": cols[1], "name_norm": name_norm, "aliases_norm": self._aliases(cols[3], name_norm),
                "state_code": state_code,
                "is_urban": neighbourhood or pop >= self.URBAN_POP or feature_code in self.TOWN_CODES,
                "population": pop or None, "wkt": f"POINT({float(cols[5])} {float(cols[4])})"}
