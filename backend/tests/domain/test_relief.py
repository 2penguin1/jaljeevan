import pytest

from app.domain.bids import BidRules, IllegalBidAction
from app.domain.matching import Vendor, match_vendors, suggested_price
from app.domain.relief import relief_need


def test_relief_need_is_rural_people_times_litres_times_tanker_share():
    need = relief_need(population=381611, population_urban=81621, share=0.10)
    assert need.people == 29999                     # 10% of 2,99,990 rural people
    assert need.kl_per_day == 600.0                 # x 20 litres = 5,99,980 L -> 600 kL (rounded up)
    assert need.tanker_trips_per_day == 60          # 10 kL tankers
    assert "20 L" in need.formula and "10%" in need.formula


def test_without_an_urban_split_the_whole_zone_counts():
    assert relief_need(population=1000, population_urban=None, share=0.5).people == 500


ZONE = (17.53, 76.21)  # Akkalkot
VENDORS = [
    Vendor("near-cheap", 17.60, 76.20, tanker_count=12, capacity_kl=10, price=55, reliability=0.9),
    Vendor("near-pricey", 17.50, 76.30, tanker_count=8, capacity_kl=10, price=80, reliability=0.95),
    Vendor("far", 19.0, 73.0, tanker_count=40, capacity_kl=12, price=50, reliability=0.9),   # ~380 km
    Vendor("no-tankers", 17.55, 76.22, tanker_count=0, capacity_kl=10, price=40, reliability=1.0),
]


def test_matching_keeps_vendors_in_reach_with_tankers_and_ranks_them_with_reasons():
    ranked = match_vendors(ZONE, VENDORS, radius_km=100, need_kl_per_day=600)
    assert [m.vendor.key for m in ranked] == ["near-cheap", "near-pricey"]
    best = ranked[0]
    assert best.road_km == pytest.approx(best.road_km) and best.road_km < 15
    assert "km" in best.reason and "₹55/kL" in best.reason and "12 tankers" in best.reason and "90%" in best.reason


def test_suggested_price_is_the_median_of_vendors_in_reach():
    ranked = match_vendors(ZONE, VENDORS, radius_km=100, need_kl_per_day=600)
    assert suggested_price(ranked) == 67.5
    assert suggested_price([]) == 60.0


def test_bids_take_turns_and_end_when_accepted_or_declined():
    rules = BidRules()
    assert rules.next("invited", "vendor", "vendor", "counter") == ("countered", "gov")
    assert rules.next("countered", "gov", "gov", "counter") == ("countered", "vendor")
    assert rules.next("countered", "vendor", "vendor", "accept") == ("accepted", "none")
    with pytest.raises(IllegalBidAction):
        rules.next("countered", "gov", "vendor", "accept")      # not the vendor's turn
    with pytest.raises(IllegalBidAction):
        rules.next("accepted", "none", "gov", "counter")         # finished
    with pytest.raises(IllegalBidAction):
        rules.next("invited", "vendor", "vendor", "haggle")      # unknown action
