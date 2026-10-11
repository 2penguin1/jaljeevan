"""How much drinking water a drought zone needs from tankers. Pure arithmetic, shown to the user with its formula."""
import math
from dataclasses import dataclass

LITRES_PER_PERSON_DAY = 20   # drinking-water tanker norm used by state drought plans
TANKER_KL = 10               # a standard water tanker


@dataclass(frozen=True)
class ReliefNeed:
    people: int
    kl_per_day: float
    tanker_trips_per_day: int
    share: float
    formula: str


def relief_need(population: int | None, population_urban: int | None, share: float = 0.10) -> ReliefNeed:
    """People who depend on tankers = rural people in the dry parts x share (urban taps are a separate system)."""
    rural = max(0, (population or 0) - (population_urban or 0))
    people = int(rural * share)
    kl = float(math.ceil(people * LITRES_PER_PERSON_DAY / 1000))
    trips = math.ceil(kl / TANKER_KL)
    formula = (f"{rural:,} rural people x {share:.0%} on tankers x {LITRES_PER_PERSON_DAY} L a day = {kl:,.0f} kL a day"
               f" = {trips:,} trips of a {TANKER_KL} kL tanker")
    return ReliefNeed(people, kl, trips, share, formula)
