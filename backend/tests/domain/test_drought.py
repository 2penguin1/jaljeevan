from datetime import date

import pytest

from app.domain.drought import (FOOTPRINT_LABEL, DroughtInputs, DroughtRules, dekad_end, pentad_end, pentad_of)

TODAY = date(2026, 10, 11)
FRESH = date(2026, 10, 5)


def assess(spi_6p=None, spi_18p=None, soil=None, declared=None, imd=None, spi_period=FRESH, soil_period=FRESH):
    return DroughtRules().assess(DroughtInputs(spi_6p=spi_6p, spi_18p=spi_18p, spi_period=spi_period,
                                               soil_anomaly=soil, soil_period=soil_period, imd_departure_pct=imd,
                                               declared_severity=declared, today=TODAY))


@pytest.mark.parametrize("spi_6p, spi_18p, expected", [
    (0.2, 0.1, False),     # normal rain, no dry spell
    (-1.2, 0.0, True),     # dry spell (a very dry month) even with a normal season
    (0.0, -1.2, False),    # season deficit without a dry spell: not enough on its own...
    (0.0, -1.6, True),     # ...unless the deficit is severe
    (-1.1, -1.1, True),    # deficit with dry spell
])
def test_trigger_one_follows_the_manual(spi_6p, spi_18p, expected):
    assert assess(spi_6p, spi_18p).trigger1 is expected


@pytest.mark.parametrize("spi_6p, spi_18p, soil, level", [
    (0.0, 0.0, -2.0, "none"),        # rainfall trigger not met: soil alone never declares drought
    (-1.2, -0.5, None, "watch"),     # moderate trigger, soil unknown
    (-1.7, -1.6, None, "moderate"),  # severe trigger, soil unknown
    (-1.2, -0.5, 0.3, "watch"),      # trigger met but soil is normal
    (-1.2, -0.5, -1.2, "moderate"),  # soil moderately dry
    (-1.2, -0.5, -1.8, "moderate"),  # moderate trigger + severe soil
    (-1.7, -1.6, -1.8, "severe"),    # severe trigger + severe soil
])
def test_level_table(spi_6p, spi_18p, soil, level):
    assert assess(spi_6p, spi_18p, soil).level == level


def test_boost_and_reasons_follow_the_level():
    severe = assess(-1.7, -2.73, -1.8)
    # data alone stays below the activation score (60): a zone goes live only with ground reports or a declaration
    assert severe.boost == 0.55 and severe.t1_class == "severe" and severe.soil_class == "severe"
    assert assess(0.0, 0.0, declared="severe").boost == 0.6 and assess(-1.7, -2.73, -1.8, declared="moderate").boost == 0.6
    assert any("−2.7" in r or "-2.7" in r for r in severe.reasons) and len(severe.reasons) >= 2
    assert assess(0.0, 0.0).boost == 0.0 and assess(0.0, 0.0).reasons == ()


def test_stale_data_counts_as_unknown():
    old = assess(-1.7, -1.6, -1.8, spi_period=date(2026, 9, 1), soil_period=date(2026, 9, 1))
    assert old.level == "none" and old.trigger1 is False
    soil_old = assess(-1.7, -1.6, -1.8, soil_period=date(2026, 9, 1))  # soil may be up to 30 days old
    assert soil_old.soil_class is None and soil_old.level == "moderate"
    soil_ok = assess(-1.7, -1.6, -1.8, soil_period=date(2026, 9, 20))
    assert soil_ok.level == "severe"


def test_an_official_declaration_lifts_the_level_but_never_lowers_it():
    assert assess(0.0, 0.0, declared="severe").level == "severe"
    assert assess(0.0, 0.0, declared="moderate").level == "moderate"
    assert assess(-1.7, -1.6, -1.8, declared="moderate").level == "severe"
    assert assess(declared="moderate", spi_period=None).declared == "moderate"


def test_imd_is_shown_as_a_cross_check_only():
    assert assess(0.0, 0.0, imd=-60).level == "none" and assess(0.0, 0.0, imd=-60).imd_deficient is True
    assert assess(-1.2, -0.5, imd=5).imd_deficient is False


def test_pentads_and_dekads():
    assert pentad_end(2026, 55) == date(2026, 10, 5)
    assert pentad_end(2026, 72) == date(2026, 12, 31)
    assert pentad_end(2026, 12) == date(2026, 2, 28)
    assert pentad_of(date(2026, 10, 7)) == 56
    assert dekad_end(date(2026, 9, 11)) == date(2026, 9, 20)
    assert dekad_end(date(2026, 9, 21)) == date(2026, 9, 30)


def test_label_never_claims_to_be_official():
    assert "Indicative" in FOOTPRINT_LABEL and "official" not in FOOTPRINT_LABEL.lower()
