from app.domain.plan_menu import MENU, plan_options


def test_quantities_and_costs_come_from_the_zone_size_and_the_unit_cost_table():
    options = plan_options("drought", ["farm_ponds", "check_dams", "space_elevator"], rural_people=300_000)
    assert [o.key for o in options] == ["farm_ponds", "check_dams"]          # only menu items
    villages = 300_000 // 1500                                               # 200 villages at the norm
    ponds = next(o for o in options if o.key == "farm_ponds")
    assert ponds.quantity == villages * MENU["drought"]["farm_ponds"].per_village
    assert ponds.cost_inr == ponds.quantity * MENU["drought"]["farm_ponds"].unit_cost_inr
    assert "per village" in ponds.basis


def test_a_zone_always_counts_at_least_one_village():
    [o] = plan_options("drought", ["check_dams"], rural_people=10)
    assert o.quantity >= 1
