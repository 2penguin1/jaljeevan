"""One place that turns stored data into a drought assessment per taluka.

Zone detection, the map footprint and the zone page all call this, so they can never disagree.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.drought import DroughtAssessment, DroughtInputs, DroughtRules
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.repositories.declaration_repository import DeclarationRepository
from app.repositories.indicator_repository import IndicatorRepository

DECLARATION_VALID = timedelta(days=183)  # the manual: a declaration holds for up to six months


@dataclass(frozen=True)
class AreaDrought:
    area_id: int
    assessment: DroughtAssessment
    metrics: dict = field(default_factory=dict)  # raw values behind the assessment, for the zone page


class DroughtAssessor:
    def __init__(self, area_indicators: AreaIndicatorRepository, indicators: IndicatorRepository,
                 declarations: DeclarationRepository, areas: AdminAreaRepository, rules: DroughtRules):
        self.area_indicators = area_indicators
        self.indicators = indicators
        self.declarations = declarations
        self.areas = areas
        self.rules = rules

    def assess(self, now: datetime, area_ids: list[int] | None = None) -> dict[int, AreaDrought]:
        spi = self.area_indicators.latest("chirps-spi", area_ids)
        soil = self.area_indicators.latest("gdo-soil", area_ids)
        declared = self.declarations.active(since=(now - DECLARATION_VALID).date())
        if area_ids is not None:
            declared = {a: d for a, d in declared.items() if a in set(area_ids)}
        ids = set(spi) | set(soil) | set(declared)
        if not ids:
            return {}
        parents = self.areas.parent_ids(list(ids))
        imd = self.indicators.latest_by_district("imd")
        out: dict[int, AreaDrought] = {}
        for area_id in ids:
            s, w, d = spi.get(area_id, {}), soil.get(area_id, {}), declared.get(area_id)
            district_imd = imd.get(parents.get(area_id)) or {}
            inputs = DroughtInputs(spi_6p=s.get("spi_6p"), spi_18p=s.get("spi_18p"), spi_period=s.get("period"),
                                   soil_anomaly=w.get("soil_anomaly"), soil_period=w.get("period"),
                                   imd_departure_pct=district_imd.get("rainfall_departure_pct"),
                                   declared_severity=d.severity if d else None, today=now.date())
            metrics = {**{k: v for k, v in s.items() if k != "period"}, "spi_period": s.get("period"),
                       "soil_anomaly": w.get("soil_anomaly"), "soil_period": w.get("period"),
                       "imd_departure_pct": inputs.imd_departure_pct, "declaration": d}
            out[area_id] = AreaDrought(area_id, self.rules.assess(inputs), metrics)
        return out
