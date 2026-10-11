"""Long-term plan options: a fixed menu per hazard, with quantities and costs computed in code.

Quantities scale with the zone's estimated number of villages (rural people / an average village size) times a
per-village planning norm; cost = quantity x unit cost. The norms and unit costs below are INDICATIVE DEMO ASSUMPTIONS
for planning conversations, not official schedule-of-rates figures; the UI says so next to every number.
"""
import math
from dataclasses import dataclass

VILLAGE_SIZE = 1500  # people in an average village (planning assumption)


@dataclass(frozen=True)
class MenuItem:
    label: str
    unit: str
    unit_cost_inr: int
    per_village: float


@dataclass(frozen=True)
class PlanOption:
    key: str
    label: str
    unit: str
    quantity: int
    unit_cost_inr: int
    cost_inr: int
    basis: str


MENU: dict[str, dict[str, MenuItem]] = {
    "drought": {
        "farm_ponds": MenuItem("Farm ponds to store monsoon run-off", "pond", 150_000, 5),
        "check_dams": MenuItem("Check dams on seasonal streams", "dam", 1_000_000, 0.25),
        "recharge_pits": MenuItem("Borewell recharge pits", "pit", 50_000, 4),
        "village_tanks": MenuItem("Covered village drinking-water tanks", "tank", 800_000, 0.5),
        "drip_irrigation": MenuItem("Drip irrigation support for small farmers", "hectare", 60_000, 10),
    },
    "water": {
        "pipeline_renewal": MenuItem("Replace leaking distribution mains", "km", 2_500_000, 0.5),
        "storage_reservoirs": MenuItem("Elevated storage reservoirs", "reservoir", 4_000_000, 0.1),
        "household_meters": MenuItem("Household water meters", "meter", 3_000, 50),
    },
    "flood": {
        "drainage": MenuItem("Storm-water drains in low-lying areas", "km", 3_000_000, 0.3),
        "raised_shelters": MenuItem("Raised community flood shelters", "shelter", 2_500_000, 0.1),
        "early_warning": MenuItem("River level sensors and sirens", "station", 400_000, 0.2),
    },
    "heat": {
        "cool_roofs": MenuItem("Cool roofs on homes and schools", "roof", 15_000, 30),
        "shade_trees": MenuItem("Shade trees along streets and markets", "tree", 1_500, 200),
        "water_kiosks": MenuItem("Public drinking-water kiosks", "kiosk", 200_000, 1),
    },
}


def villages(rural_people: int) -> int:
    return max(1, rural_people // VILLAGE_SIZE)


def plan_options(hazard: str, keys: list[str], rural_people: int) -> list[PlanOption]:
    menu = MENU.get(hazard, {})
    n = villages(rural_people)
    out = []
    for key in dict.fromkeys(k for k in keys if k in menu):
        item = menu[key]
        qty = max(1, math.ceil(n * item.per_village))
        out.append(PlanOption(key, item.label, item.unit, qty, item.unit_cost_inr, qty * item.unit_cost_inr,
                              f"{n:,} villages x {item.per_village:g} {item.unit} per village x "
                              f"₹{item.unit_cost_inr:,} each (indicative)"))
    return out
