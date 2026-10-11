from app.domain.playbook import PLAYBOOK, keep_actions, without_numbers


def test_only_actions_from_the_hazard_playbook_survive_in_order_without_repeats():
    keys = list(PLAYBOOK["drought"])
    assert keep_actions("drought", [keys[1], "build_a_dam_tomorrow", keys[0], keys[1]]) == [keys[1], keys[0]]
    assert keep_actions("unknown-hazard", keys) == []


def test_sentences_with_numbers_are_removed_because_numbers_come_from_code():
    text = "Wells have dried up across the taluka. About 40,000 people need water. Farmers report losing their kharif crop."
    assert without_numbers(text) == "Wells have dried up across the taluka. Farmers report losing their kharif crop."
    assert without_numbers("२५ गावे कोरडी. Wells are dry.") == "Wells are dry."  # Indian digits count too
