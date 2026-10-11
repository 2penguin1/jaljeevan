"""Turns the latest drought rasters into per-taluka values in area_indicators.

Runs inside every pipeline run but only downloads when a source has a newer period than the one stored, so
extra runs are cheap. Each source is isolated: one failing source never blocks the others.
"""
import logging
from datetime import datetime

import numpy as np

from app.core.exceptions import ExternalServiceError
from app.domain.drought import DroughtRules, dekad_end, pentad_end
from app.domain.text import TextFingerprinter
from app.integrations.population import WorldPopGrid
from app.integrations.raster import Grid, resample_nearest, shapes_from_wkb, zonal_mean, zonal_sums
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.repositories.indicator_repository import IndicatorRepository

LOG = logging.getLogger(__name__)
SPI_SOURCE, SOIL_SOURCE = "chirps-spi", "gdo-soil"
_NAMES = TextFingerprinter()


class IndicatorRefreshService:
    def __init__(self, area_indicators: AreaIndicatorRepository, areas: AdminAreaRepository, chirps, soil,
                 population: WorldPopGrid | None, imd=None, indicators: IndicatorRepository | None = None):
        self.imd = imd                # optional cross-check: official IMD district departure
        self.indicators = indicators  # district_indicators, where the IMD value is stored
        self.area_indicators = area_indicators
        self.areas = areas
        self.chirps = chirps
        self.soil = soil
        self.population = population

    def refresh(self, now: datetime) -> dict:
        stats: dict = {}
        if self.imd is not None and self.indicators is not None:
            stats["imd"] = self._imd()  # district level: does not need talukas
        shapes = shapes_from_wkb(self.areas.geometries("subdistrict"))
        if not shapes:
            return {**stats, "skipped": "no talukas loaded"}
        for name, step in ((SPI_SOURCE, self._spi), (SOIL_SOURCE, self._soil)):
            try:
                stats[name] = step(shapes)
            except ExternalServiceError as exc:
                LOG.warning("indicator source %s failed: %s", name, exc)
                stats[name] = {"error": str(exc)}
        return stats

    def _imd(self) -> dict:
        readings = self.imd.fetch()  # fails soft: [] when the page is down or changed
        if not readings:
            return {"skipped": "no readings"}
        day = max(r.day for r in readings)
        if self.indicators.has_period("imd", day):
            return {"skipped": "fresh", "day": day.isoformat()}
        matched = 0
        for r in readings:
            ids = self.areas.district_ids_by_name(_NAMES.norm_name(r.district))
            if len(ids) == 1:  # the page has no state names: a name found in two states is skipped, not guessed
                self.indicators.upsert(ids[0], r.day, "imd", rainfall_departure_pct=r.departure_pct)
                matched += 1
        return {"day": day.isoformat(), "matched": matched, "unmatched": len(readings) - matched}

    def _spi(self, shapes) -> dict:
        latest = self.chirps.latest("18")
        if latest is None:
            return {"skipped": "no files listed"}
        period = pentad_end(*latest)
        if self._is_fresh(SPI_SOURCE, period):
            return {"skipped": "fresh", "period": period.isoformat()}
        season = self.chirps.fetch("18", *latest)
        month = self.chirps.fetch("06", *latest)
        rows = [(a, period, SPI_SOURCE, "spi_18p", v) for a, v in zonal_mean(season, shapes).items()]
        rows += [(a, period, SPI_SOURCE, "spi_6p", v) for a, v in zonal_mean(month, shapes).items()]
        rows += self._people_in_dry_cells(season, month, shapes, period)
        self.area_indicators.upsert_many(rows)
        return {"period": period.isoformat(), "areas": len({r[0] for r in rows})}

    def _people_in_dry_cells(self, season: Grid, month: Grid, shapes, period) -> list:
        """People living in grid cells that meet the rainfall trigger themselves (dry month, or severe season
        deficit), so a taluka's 'people affected' excludes its parts that got normal rain."""
        pop = self.population.grid if self.population is not None else None
        if pop is None:
            return []
        rules = DroughtRules
        month_on_pop = resample_nearest(month, pop.transform, pop.shape)
        season_on_pop = resample_nearest(season, pop.transform, pop.shape)
        with np.errstate(invalid="ignore"):
            dry = (month_on_pop <= rules.SPI_MODERATE) | (season_on_pop <= rules.SPI_SEVERE)
        total = zonal_sums(pop, shapes, mask=dry)
        urban = zonal_sums(pop, shapes, mask=dry & self.population.urban_mask)
        return ([(a, period, SPI_SOURCE, "pop_stressed", v) for a, v in total.items()]
                + [(a, period, SPI_SOURCE, "pop_stressed_urban", v) for a, v in urban.items()])

    def _soil(self, shapes) -> dict:
        start = self.soil.latest()
        if start is None:
            return {"skipped": "no files listed"}
        period = dekad_end(start)
        if self._is_fresh(SOIL_SOURCE, period):
            return {"skipped": "fresh", "period": period.isoformat()}
        rows = [(a, period, SOIL_SOURCE, "soil_anomaly", v)
                for a, v in zonal_mean(self.soil.fetch(start), shapes).items()]
        self.area_indicators.upsert_many(rows)
        return {"period": period.isoformat(), "areas": len(rows)}

    def _is_fresh(self, source: str, period) -> bool:
        stored = self.area_indicators.latest_period(source)
        return stored is not None and stored >= period
