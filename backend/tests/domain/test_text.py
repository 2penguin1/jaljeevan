from app.domain.text import TextFingerprinter

fp = TextFingerprinter()

BODY = (
    "Residents of several wards in Mahadevapura said municipal water supply has been cut for "
    "eleven days and private tanker prices have doubled to two thousand rupees per load. "
    "Officials of the water board said borewells in the area have dried up after a weak "
    "monsoon and that additional tankers will be deployed from Monday. Apartment associations "
    "have started rationing water and some families are buying cans for drinking. "
) * 2


def test_clean_strips_tags_and_entities():
    assert fp.clean("<p>No&nbsp;water <b>today</b></p>") == "No water today"


def test_fold_is_nfc_casefold():
    assert fp.fold("ＷＡＴＥＲ Crisis") == fp.fold("ＷＡＴＥＲ crisis")
    assert fp.fold("पानी") == "पानी"


def test_content_hash_ignores_whitespace_and_case():
    assert fp.content_hash("No  water <i>here</i>") == fp.content_hash("no water here")


def test_norm_name():
    assert fp.norm_name("  Sri Ganganagar, (Raj.) ") == "sri ganganagar raj"


def test_simhash_near_duplicate_wire_story():
    a = fp.simhash("Bengaluru water crisis deepens. " + BODY)
    b = fp.simhash("Water crisis deepens in Bengaluru as taps run dry. " + BODY)
    assert fp.is_near_duplicate(a, b)


def test_simhash_unrelated_texts_are_far():
    a = fp.simhash(BODY)
    b = fp.simhash("The cricket team won the final in Chennai with a last-ball six, and fans "
                   "celebrated through the night across the city streets and stadium gates. " * 3)
    assert fp.hamming(a, b) > 16 and not fp.is_near_duplicate(a, b)


def test_simhash_fits_signed_bigint():
    h = fp.simhash(BODY)
    assert -(2**63) <= h < 2**63
