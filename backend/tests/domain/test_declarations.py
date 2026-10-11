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
