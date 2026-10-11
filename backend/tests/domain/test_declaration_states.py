from app.domain.declaration_states import WATCH_STATES, list_sentences, pick_state

SIASAT = (
    "Bengaluru: The number of drought-affected taluks in Karnataka has risen to 217 after the state government added "
    "another 40 taluks to the list. The latest decision means that just 23 of the state's 240 taluks are currently "
    "outside the drought-hit category.\n"
    "The 40 taluks added in the latest phase are Channapatna, Kanakapura, Harohalli, Jagalur, Piriyapatna, Kushtagi, "
    "Aurad, Gokak, Ramdurg, Savadatti, Kagwad, Indi, Chadachan, Talikote, Gadag, Mundargi, Ron, Hirekerur, Dharwad, "
    "Kalghatgi, Kundgol, Alnavar, Bhadravati, Shikaripura, Shivamogga, Soraba, Thirthahalli, Chikkamagaluru, Kalasa, "
    "Madikeri, Kushalnagar, Belthangady, Bantwal, Ullal, Udupi, Byndoor, Ankola, Bhatkal, Haliyal and Sirsi.\n"
    "The government's decision follows a series of drought declarations made after detailed assessments."
)


def names(text):
    return [n for s in list_sentences(text) for n in s.names]


def test_the_list_sentence_of_a_real_article_gives_every_name_cleanly():
    found = names(SIASAT)
    assert len(found) == 40
    assert found[0] == "Channapatna" and found[-2:] == ["Haliyal", "Sirsi"]


def test_a_single_taluka_sentence_is_a_list_of_one():
    assert names("Gadag taluk was declared drought-hit on Thursday.") == ["Gadag"]
    assert names("Gadag taluk is now declared drought-hit.") == ["Gadag"]


def test_a_declaring_heading_line_introduces_the_list_on_the_next_line():
    text = "The following taluks have been declared drought-hit:\nAthani, Chikkodi & Raibag."
    assert names(text) == ["Athani", "Chikkodi", "Raibag"]


def test_demands_maybes_and_exclusions_are_not_declarations():
    for text in ("Karnataka estimates crop loss as 220 taluks may be declared drought-hit: Afzalpur, Aland, Jevargi.",
                 "KPRS demands that the government declare these taluks drought-hit: Afzalpur, Aland, Jevargi.",
                 "Farmers complain of crop loss in excluded talukas from the drought list: Karveer, Shirol, Hatkanangale.",
                 "आणखी १९ तालुक्यांमध्ये दुष्काळ जाहीर करण्याच्या मागणीच्या पार्श्वभूमीवर: मुदखेड, मुखेड, अर्धापूर"):
        assert names(text) == [], text


def test_counts_without_names_give_nothing():
    assert names("The govt had declared 101 taluks drought-hit in the first phase on Aug 27.") == []


def test_the_state_needs_most_matches_and_its_name_in_the_article():
    ka = next(s for s in WATCH_STATES if s.code == "KA")
    assert pick_state({"KA": (5, 6), "AP": (1, 6)}, "Drought in Karnataka") == ka
    assert pick_state({"KA": (5, 6)}, "Drought in the south") is None          # never guessed from names alone
    assert pick_state({"KA": (3, 6), "AP": (3, 6)}, "Karnataka and Andhra") is None  # no clear winner
    assert pick_state({"KA": (2, 2)}, "Karnataka and Kerala") is None          # few names, two states named
    assert pick_state({"KA": (4, 6)}, "K'taka govt adds taluks") == ka         # press short form


def test_telangana_mandals_are_matched_in_the_old_andhra_pradesh_boundaries():
    tg = next(s for s in WATCH_STATES if s.code == "TG")
    assert tg.pool == "AP"
    assert "MH" not in {s.code for s in WATCH_STATES} and "BR" not in {s.code for s in WATCH_STATES}


def test_future_and_not_yet_are_not_declarations():
    for text in ("Taluks to be added in the next phase are Afzalpur, Aland, Jevargi and Sedam.",
                 "The government will declare these taluks drought-hit: Afzalpur, Aland, Jevargi.",
                 "Taluks not yet declared include Afzalpur, Aland and Jevargi."):
        assert names(text) == [], text


def test_one_taluka_counts_when_the_article_names_only_that_state():
    assert pick_state({"KA": (1, 1)}, "Indi taluk added to the Karnataka drought list") is not None
    assert pick_state({"KA": (1, 1)}, "Karnataka and Telangana farmers") is None  # two states named: unsure
    assert pick_state({"KA": (1, 2), "AP": (1, 2)}, "Karnataka news") is None


def test_dates_written_in_orders_are_found():
    from datetime import date
    from app.domain.declaration_states import order_dates
    assert order_dates("No. RD 12 2023, dated 12/09/2023. Bengaluru, 28 September 2026") == [date(2023, 9, 12),
                                                                                            date(2026, 9, 28)]
    assert order_dates("दिनांक : २५.०९.२०२६") == [date(2026, 9, 25)]
    assert order_dates("No date here, 2026 only") == []
