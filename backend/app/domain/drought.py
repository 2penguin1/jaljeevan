"""Drought rules from the Government of India Manual for Drought Management (2016, revised 2020). Pure domain.

Trigger 1 (the manual's rainfall test, 2016 Table 3.10):
  - a dry spell triggers it, even when the season total is normal;
  - a rainfall deficit triggers it only together with a dry spell, or when the deficit is severe (SPI <= -1.5).
  We read the season deficit from the 3-month SPI (CHIRPS 18-pentad) and use the 1-month SPI (6-pentad) <= -1 as
  the dry-spell proxy.
  ponytail: the manual's dry spell is "3-4 weeks each below 50% of normal"; daily CHIRPS percent-of-normal is the
  exact upgrade.
Impact: soil moisture. The manual grades soil moisture as a percentage of available water (PASM/MAI). We use the
  Copernicus GDO soil moisture *anomaly* (standardised like SPI): <= -1 moderate, <= -1.5 severe. That mapping is
  ours, so the label says "soil moisture anomaly".
Confirmation: data alone gives at most a watch-level score; posts from the area or a declaration make it active.
Combination (our reading of the 2020 "2 of 3 impacts" rule with one impact available):
  trigger not met -> none; met and soil unknown -> watch (moderate trigger) / moderate (severe trigger);
  soil normal -> watch; soil moderate -> moderate; severe trigger and severe soil -> severe.
An official state declaration lifts the level to at least the declared severity; it never lowers it.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

RULES_VERSION = "gom2016-t1+soil.v1"
FOOTPRINT_LABEL = "Indicative drought footprint (GoI Drought Manual, rainfall trigger + soil moisture anomaly)"

LEVELS = ("none", "watch", "moderate", "severe")


def pentad_end(year: int, pentad: int) -> date:
    """CHIRPS pentads: 6 per month, the last one runs to the month's end (p55 = 1-5 Oct)."""
    month, k = (pentad - 1) // 6 + 1, (pentad - 1) % 6
    last = calendar.monthrange(year, month)[1] if k == 5 else 5 * k + 5
    return date(year, month, last)


def pentad_of(day: date) -> int:
    return (day.month - 1) * 6 + min(5, (day.day - 1) // 5) + 1


def dekad_end(start: date) -> date:
    """GDO dekads start on the 1st, 11th and 21st; the third runs to the month's end."""
    if start.day >= 21:
        return date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    return start + timedelta(days=9)


@dataclass(frozen=True)
class DroughtInputs:
    spi_6p: float | None          # ~1-month SPI (dry-spell proxy)
    spi_18p: float | None         # ~3-month SPI (season deficit)
    spi_period: date | None       # last day the SPI covers
    soil_anomaly: float | None
    soil_period: date | None
    imd_departure_pct: float | None  # district rainfall vs normal, cross-check only
    declared_severity: str | None    # official declaration: "moderate" | "severe" | None
    today: date


@dataclass(frozen=True)
class DroughtAssessment:
    level: str                       # none | watch | moderate | severe
    trigger1: bool
    t1_class: str | None             # moderate | severe (when triggered)
    soil_class: str | None           # none | moderate | severe; None = unknown or stale
    boost: float                     # feeds ZoneScorer.score as indicator support
    reasons: tuple[str, ...] = field(default_factory=tuple)
    declared: str | None = None
    imd_deficient: bool | None = None
    stale: bool = False              # rainfall data missing or too old: "unknown", never "the rain came back"


class DroughtRules:
    SPI_MODERATE, SPI_SEVERE = -1.0, -1.5
    SOIL_MODERATE, SOIL_SEVERE = -1.0, -1.5
    IMD_DEFICIENT = -20.0            # IMD "deficient" starts at 20% below normal
    MAX_SPI_AGE_DAYS = 20
    MAX_SOIL_AGE_DAYS = 30           # the soil product's mirror runs ~3 weeks behind
    # Data alone stays below the activation score (60): like the manual's ground-truthing step, a drought zone
    # goes live only when posts from the area confirm it, or the state has declared it.
    BOOST = {"none": 0.0, "watch": 0.2, "moderate": 0.4, "severe": 0.55}
    DECLARED_BOOST = 0.6

    def assess(self, x: DroughtInputs) -> DroughtAssessment:
        reasons: list[str] = []
        spi_ok = self._fresh(x.spi_period, x.today, self.MAX_SPI_AGE_DAYS)
        dry_spell = spi_ok and x.spi_6p is not None and x.spi_6p <= self.SPI_MODERATE
        severe_deficit = spi_ok and x.spi_18p is not None and x.spi_18p <= self.SPI_SEVERE
        trigger1 = dry_spell or severe_deficit
        t1_class = None
        if trigger1:
            worst = min(v for v in (x.spi_6p, x.spi_18p) if v is not None)
            t1_class = "severe" if worst <= self.SPI_SEVERE else "moderate"
            if severe_deficit:
                reasons.append(f"Rainfall over the last 3 months is severely below normal (SPI {x.spi_18p:.1f})")
            if dry_spell:
                reasons.append(f"The last month was very dry (SPI {x.spi_6p:.1f})")

        soil_class = None
        if self._fresh(x.soil_period, x.today, self.MAX_SOIL_AGE_DAYS) and x.soil_anomaly is not None:
            soil_class = ("severe" if x.soil_anomaly <= self.SOIL_SEVERE
                          else "moderate" if x.soil_anomaly <= self.SOIL_MODERATE else "none")
            if trigger1 and soil_class != "none":
                reasons.append(f"Soil is {soil_class}ly drier than normal (anomaly {x.soil_anomaly:.1f})")

        level = self._level(trigger1, t1_class, soil_class)
        if x.declared_severity in ("moderate", "severe") and LEVELS.index(x.declared_severity) > LEVELS.index(level):
            level = x.declared_severity
        if x.declared_severity:
            reasons.append(f"Officially declared ({x.declared_severity}) by the state government")
        imd = None if x.imd_departure_pct is None else x.imd_departure_pct <= self.IMD_DEFICIENT
        boost = max(self.BOOST[level], self.DECLARED_BOOST) if x.declared_severity else self.BOOST[level]
        return DroughtAssessment(level=level, trigger1=trigger1, t1_class=t1_class, soil_class=soil_class,
                                 boost=boost, reasons=tuple(reasons) if level != "none" else (),
                                 declared=x.declared_severity, imd_deficient=imd, stale=not spi_ok)

    @staticmethod
    def _level(trigger1: bool, t1_class: str | None, soil_class: str | None) -> str:
        if not trigger1:
            return "none"
        if soil_class is None:
            return "moderate" if t1_class == "severe" else "watch"
        if soil_class == "none":
            return "watch"
        if soil_class == "severe" and t1_class == "severe":
            return "severe"
        return "moderate"

    @staticmethod
    def _fresh(period: date | None, today: date, max_age: int) -> bool:
        return period is not None and (today - period).days <= max_age
