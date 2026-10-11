import pytest

from app.domain.declarations import (TalukaMatcher, latin_key, looks_garbled, severity_from_text, transliterate)

TALUKAS = [(1, "Mohol", "Solapur"), (2, "Akkalkot", "Solapur"), (3, "Sangola", "Solapur"),
           (4, "Mohol", "Elsewhere"), (5, "Barshi", "Solapur")]


@pytest.mark.parametrize("marathi, english", [
    ("सोलापूर", "Solapur"),
    ("मोहोळ", "Mohol"),
    ("अक्कलकोट", "Akkalkot"),
    ("बार्शी", "Barshi"),
])
def test_marathi_names_transliterate_close_to_their_english_spelling(marathi, english):
    from rapidfuzz import fuzz
    assert fuzz.ratio(latin_key(transliterate(marathi)), latin_key(english)) >= 85


def test_matcher_prefers_the_named_district_and_scores_confidence():
    m = TalukaMatcher(TALUKAS)
    hit = m.match("मोहोळ", district="Solapur")
    assert hit.area_id == 1 and hit.score >= 85
    assert m.match("अक्कलकोट").area_id == 2
    assert m.match("Sangola").area_id == 3                 # English names work too (Karnataka lists)
    weak = m.match("पुणे")                                  # not in the list
    assert weak is None or weak.score < m.ACCEPT


def test_severity_words_after_translation():
    assert severity_from_text("Severe drought has been declared in these talukas") == "severe"
    assert severity_from_text("Serious drought") == "severe"
    assert severity_from_text("moderate drought") == "moderate"
    assert severity_from_text("Drought declared") is None


def test_garbled_pdf_text_is_detected_so_ocr_can_take_over():
    assert looks_garbled("ÌÉÉåÉ uÉÑ¹ÉÉ ºÉÉåsÉÉ ´ÉÉ¶É") is True     # legacy-font Marathi extracted as Latin-1 junk
    assert looks_garbled("सोलापूर जिल्ह्यातील मोहोळ तालुका") is False
    assert looks_garbled("Drought declared in 265 talukas") is False


def test_same_named_talukas_without_a_clear_district_go_to_review():
    m = TalukaMatcher(TALUKAS)  # two "Mohol": Solapur and Elsewhere
    assert m.match("मोहोळ").score < m.ACCEPT                       # no district given: ambiguous
    assert m.match("Mohol", district="ÌÉÉåÉ").score < m.ACCEPT      # district garbled: ambiguous
    assert m.match("मोहोळ", district="Puneeee").score < m.ACCEPT    # district matches nothing
    assert m.match("मोहोळ", district="Solapur").score >= m.ACCEPT   # the district settles it
    assert m.match("अक्कलकोट").score >= m.ACCEPT                    # a unique name is still fine


def test_severity_is_read_from_marathi_words_without_translation():
    assert severity_from_text("गंभीर दुष्काळ") == "severe"
    assert severity_from_text("मध्यम स्वरूपाचा दुष्काळ") == "moderate"


def test_names_broken_by_government_pdf_fonts_still_match():
    """Many GR PDFs map glyphs wrongly: ि comes out as a stray ज before the letter, ग as र्."""
    m = TalukaMatcher([(10, "Sangola", "Solapur"), (11, "Gangakhed", "Parbhani"), (12, "Shirur", "Pune"),
                       (13, "Sinnar", "Nashik"), (14, "Jath", "Sangli"), (15, "Mohol", "Solapur")])
    for broken, area in (("सांर्ोला", 10), ("र्ंर्ाखेड", 11), ("जशरूर", 12), ("जसन्नर", 13)):
        hit = m.match(broken)
        assert hit.area_id == area and hit.score >= m.ACCEPT, (broken, hit)
    assert m.match("जत").area_id == 14 and m.match("जत").score >= m.ACCEPT   # a real ज name is not "repaired" away
    assert m.match("मोहोळ").area_id == 15


def test_the_real_maharashtra_order_spellings_match():
    """Words exactly as they come out of the 26 Sep 2026 GR PDF (a font that mixes up न/ि and र्/ध)."""
    names = ["Jamner", "Nandgaon", "Sinnar", "Nashik", "Karjat", "Dodamarg", "Malegaon", "Jalgaon", "Chalisgaon",
             "Nevasa", "Parner", "Bhadgaon"]
    m = TalukaMatcher([(i, n, f"D{i}") for i, n in enumerate(names)])
    broken = {"जामिेर": "Jamner", "िांदगाव": "Nandgaon", "नसन्नर": "Sinnar", "नानशक": "Nashik", "कजधत": "Karjat",
              "दोडामागध": "Dodamarg", "मालेगाव": "Malegaon", "जळगाव": "Jalgaon", "चाळीसगाव": "Chalisgaon",
              "िेवासा": "Nevasa", "पारिेर": "Parner", "भडगाव": "Bhadgaon"}
    for text, name in broken.items():
        hit = m.match(text)
        assert hit.name == name and hit.score >= m.ACCEPT, (text, hit)


def test_more_real_order_spellings_and_english_sound_alikes():
    names = ["Thane", "Shirpur", "Malshiras", "Georai", "Shevgaon", "Mangaon"]
    m = TalukaMatcher([(i, n, f"D{i}") for i, n in enumerate(names)])
    broken = {"ठार्े": "Thane",          # ण extracted as र्
              "निरपूर": "Shirpur",       # शि extracted as नि
              "माळनिरस": "Malshiras",
              "गेवराई": "Georai",        # official English drops the v
              "शेवगाव": "Shevgaon"}      # ...but keeps it here: the alternative must not hurt
    for text, name in broken.items():
        hit = m.match(text)
        assert hit.name == name and hit.score >= m.ACCEPT, (text, hit)


def test_repairs_never_auto_accept_a_coincidental_near_miss():
    """Real errors from the 26 Sep GR: जालिा (=Jalna) tied Jaoli; र्ामणगाव (=Dhamangaon) looked like Mangaon."""
    m = TalukaMatcher([(1, "Jalna", "Jalna"), (2, "Jaoli", "Satara"), (3, "Mangaon", "Raigarh"),
                       (4, "Dhamangaon Railway", "Amravati")])
    jalna = m.match("जालिा")                      # the raw spelling is impossible Devanagari: only repairs compete
    assert (jalna.name, jalna.score >= m.ACCEPT) == ("Jalna", True)
    dhamangaon = m.match("र्ामणगाव")              # broken र् = ध; official name has a suffix ("Railway")
    assert (dhamangaon.name, dhamangaon.score >= m.ACCEPT) == ("Dhamangaon Railway", True)


def test_a_first_word_alias_never_collides_with_another_taluka_or_district():
    m = TalukaMatcher([(1, "Jalgaon", "Jalgaon"), (2, "Jalgaon (Jamod)", "Buldana"), (3, "Shirur", "Pune"),
                       (4, "Shirur (Kasar)", "Bid")])
    assert (m.match("जळगाव").name, m.match("जळगाव").score >= m.ACCEPT) == ("Jalgaon", True)
    assert (m.match("शिरूर").name, m.match("शिरूर").score >= m.ACCEPT) == ("Shirur", True)


def test_more_broken_glyphs_from_the_real_gr():
    m = TalukaMatcher([(1, "Shevgaon", "Ahmednagar"), (2, "Hingoli", "Hingoli"), (3, "Sindewahi", "Chandrapur"),
                       (4, "Nevasa", "Ahmednagar")])
    for broken, name in (("िेवगाव", "Shevgaon"), ("सहगोली", "Hingoli"), ("ससदेवाही", "Sindewahi"),
                         ("िेवासा", "Nevasa")):
        hit = m.match(broken)
        assert (hit.name, hit.score >= m.ACCEPT) == (name, True), broken


def test_official_suffixes_rural_urban_north_south():
    m = TalukaMatcher([(1, "Nagpur (Rural)", "Nagpur"), (2, "Nagpur (Urban)", "Nagpur"), (3, "Shahapur", "Thane"),
                       (4, "Solapur North", "Solapur"), (5, "Solapur South", "Solapur"), (6, "Kamptee", "Nagpur")])
    for text, name in (("िागपूर", "Nagpur (Rural)"), ("िागपूर िहर", "Nagpur (Urban)"),
                       ("उ. सोलापूर", "Solapur North"), ("द. सोलापूर", "Solapur South")):
        hit = m.match(text)
        assert (hit.name, hit.score >= m.ACCEPT) == (name, True), text


def test_a_broken_i_inside_a_word_can_be_sha_too():
    m = TalukaMatcher([(1, "Washim", "Washim"), (2, "Wani", "Yavatmal"), (3, "Washi", "Osmanabad")])
    assert (m.match("वािीम").name, m.match("वािीम").score >= m.ACCEPT) == ("Washim", True)
    assert m.match("वािी").score < m.ACCEPT  # वाशी (Washi) or वानी (Wani): equally good, a neighbour or person decides


def test_two_talukas_of_one_district_read_equally_well_are_not_guessed():
    m = TalukaMatcher([(1, "Wani", "Yavatmal"), (2, "Arni", "Yavatmal")])
    assert m.match("आणी").score < m.ACCEPT  # आर्णी with its reph lost: Arni and Wani are equally close
    assert m.match("वणी").name == "Wani" and m.match("वणी").score >= m.ACCEPT


def test_a_first_word_alias_must_not_look_like_another_taluka():
    m = TalukaMatcher([(1, "Sindkhede", "Dhule"), (2, "Sindkhed Raja", "Buldana")])
    hit = m.match("ससदखेडा")  # सिंदखेडा = Sindkhede (Dhule); "Sindkhed" alone must not mean Sindkhed Raja
    assert hit.name == "Sindkhede" or hit.score < m.ACCEPT
