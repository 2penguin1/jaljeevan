import pytest

from app.domain.taxonomy import Taxonomy


def test_shipped_taxonomy_is_valid():
    tax = Taxonomy.load()
    assert {"SUPPLY", "AGRI", "FLOOD", "HEAT", "RELIEF", "HEALTH", "INFRA", "LIVELIHOOD"} <= set(tax.l1)
    assert tax.l2["SUPPLY.TANKER_DEPENDENCE"]["parent"] == "SUPPLY"
    assert len(tax.version) == 12


def test_hazards_for():
    tax = Taxonomy.load()
    assert tax.hazards_for(["RELIEF"]) == ["drought", "flood", "heat"]
    assert tax.hazards_for(["SUPPLY", "HEAT"]) == ["drought", "heat"]
    assert tax.hazards_for([]) == []


def test_parent_of_l2():
    tax = Taxonomy.load()
    assert tax.parent_of("FLOOD.WATERLOGGING") == "FLOOD"
    assert tax.parent_of("MADE.UP") is None


def test_cards_render_l1_and_l2():
    text = Taxonomy.load().cards()
    assert "## L1 SUPPLY" in text and "### L2 SUPPLY.DRY_TAPS" in text
    assert "Excludes:" in text


def test_validate_catches_bad_prefix_and_missing_fields():
    raw = {"l1": {"SUPPLY": {"name": "S", "description": "d", "hazards": ["drought"],
                             "l2": {"WRONG.X": {"name": "x", "description": "d"},
                                    "SUPPLY.Y": {"name": "y"}}}}}
    errors = Taxonomy.validate(raw)
    assert any("WRONG.X" in e for e in errors)
    assert any("SUPPLY.Y" in e and "description" in e for e in errors)


def test_validate_rejects_unknown_hazard():
    raw = {"l1": {"X": {"name": "X", "description": "d", "hazards": ["volcano"],
                        "l2": {"X.A": {"name": "a", "description": "d"}}}}}
    assert any("volcano" in e for e in Taxonomy.validate(raw))


def test_load_raises_on_invalid(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("l1: {}\n")
    with pytest.raises(ValueError):
        Taxonomy.load(p)
