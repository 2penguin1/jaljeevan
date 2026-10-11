import csv
import os
from datetime import date

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import box

from app.cli.load_declarations import load_csv
from app.domain.declarations import TalukaMatcher
from app.models import AdminArea, DroughtDeclaration
from app.services.declaration_extractor import DeclarationExtractor

TALUKAS = [(1, "Mohol", "Solapur"), (2, "Akkalkot", "Solapur"), (3, "Barshi", "Solapur"), (4, "Haveli", "Pune"),
           (5, "Mohol", "Elsewhere")]
GR_LINES = [
    "महाराष्ट्र शासन, मदत व पुनर्वसन विभाग",
    "राज्यातील तालुक्यांमध्ये दुष्काळ जाहीर करण्याबाबत",
    "जिल्हा : सोलापूर",
    "१. मोहोळ   २. अक्कलकोट",
    "गंभीर दुष्काळ : बार्शी",
    "शासन निर्णय क्रमांक : टंचाई-२०२६",
]
TRANSLATIONS = {
    "महाराष्ट्र शासन, मदत व पुनर्वसन विभाग": "Government of Maharashtra, Relief and Rehabilitation Department",
    "राज्यातील तालुक्यांमध्ये दुष्काळ जाहीर करण्याबाबत": "Regarding declaring moderate drought in talukas of the state",
    "गंभीर दुष्काळ : बार्शी": "Severe drought: Barshi",
}


class FakeTranslator:
    def __init__(self):
        self.calls = 0

    def translate(self, texts, src_lang="mr"):
        self.calls += 1
        return [TRANSLATIONS.get(t, "") for t in texts]


def extract(translator=None):
    return DeclarationExtractor(TalukaMatcher(TALUKAS), translator).extract(
        GR_LINES, state_code="MH", declared_on=date(2026, 9, 25), order_ref="GR 25 Sep 2026", source_url=None)


def test_extracts_talukas_under_their_district_with_severity_from_translation():
    result = extract(FakeTranslator())
    got = {r["taluka"]: (r["area_id"], r["severity"]) for r in result.accepted}
    assert got == {"Mohol": (1, "moderate"), "Akkalkot": (2, "moderate"), "Barshi": (3, "severe")}
    assert all(r["district"] == "Solapur" and r["confidence"] >= 85 for r in result.accepted)


def test_without_a_translator_names_match_and_marathi_severity_words_still_count():
    result = extract(None)
    got = {r["taluka"]: r["severity"] for r in result.accepted}
    # "गंभीर दुष्काळ : बार्शी" is read directly; the title's "moderate" exists only in the English translation
    assert got == {"Mohol": "unknown", "Akkalkot": "unknown", "Barshi": "severe"}


def test_loader_writes_declarations_and_reports_unmatched_rows(db, tmp_path):
    mohol = AdminArea(level="subdistrict", name="Mohol", name_norm="mohol", state_code="MH", district_name="Solapur",
                      geom=from_shape(box(75.4, 17.6, 76.0, 18.0), srid=4326))
    db.add(mohol)
    db.flush()
    path = tmp_path / "decl.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["state_code", "district", "taluka", "area_id", "declared_on", "severity",
                                           "order_ref", "source_url"])
        w.writeheader()
        w.writerow({"state_code": "MH", "district": "Solapur", "taluka": "Mohol", "area_id": "", "declared_on": "2026-09-25",
                    "severity": "moderate", "order_ref": "GR", "source_url": ""})
        w.writerow({"state_code": "MH", "district": "Nowhere", "taluka": "Atlantis", "area_id": "", "declared_on": "2026-09-25",
                    "severity": "severe", "order_ref": "GR", "source_url": ""})
    loaded, unmatched = load_csv(db, path)
    assert loaded == 1 and [u["taluka"] for u in unmatched] == ["Atlantis"]
    assert db.query(DroughtDeclaration).one().area_id == mohol.id


@pytest.mark.skipif(not os.environ.get("RUN_SLOW"), reason="downloads IndicTrans2 (~1 GB); set RUN_SLOW=1 and HF_TOKEN")
def test_real_indictrans2_translates_marathi():
    from app.core.config import settings
    from app.integrations.indictrans import IndicTranslator
    [text] = IndicTranslator(settings.hf_token).translate(["गंभीर दुष्काळ जाहीर करण्यात आला आहे."], "mr")
    assert "drought" in text.lower()


def test_english_press_list_goes_straight_to_csv_files(tmp_path):
    from app.cli.extract_declarations import run
    lines = ["Drought declared in the following taluks:", "District: Solapur", "Mohol, Barshi, Akkalkott", "Moholl"]
    out = tmp_path / "KA_2026-10-02.csv"
    result = run(lines, TALUKAS, state="KA", day=date(2026, 10, 2), order_ref="press", url=None, lang="en",
                 translate=True, out=out)
    assert {r["taluka"] for r in result.accepted} == {"Mohol", "Barshi", "Akkalkot"}
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 3 and (tmp_path / "KA_2026-10-02_check.csv").exists()


def test_a_declaration_without_a_stated_severity_loads_as_moderate(db, tmp_path):
    mohol = AdminArea(level="subdistrict", name="Mohol", name_norm="mohol", state_code="MH", district_name="Solapur",
                      geom=from_shape(box(75.4, 17.6, 76.0, 18.0), srid=4326))
    db.add(mohol)
    db.flush()
    path = tmp_path / "d.csv"
    path.write_text("state_code,district,taluka,area_id,declared_on,severity,order_ref,source_url\n"
                    "MH,Solapur,Mohol,,2026-09-25,unknown,GR 1,\n", encoding="utf-8")
    loaded, skipped = load_csv(db, path)
    row = db.query(DroughtDeclaration).one()
    assert loaded == 1 and row.severity == "moderate" and "severity not stated" in row.order_ref


def test_district_headings_are_found_even_when_the_pdf_font_breaks_them():
    lines = ["दुष्काळ जाहीर करण्याबाबत", "जजल्हा : सोलापूर", "मोहोळ"]  # जिल्हा extracted as जजल्हा
    result = DeclarationExtractor(TalukaMatcher(TALUKAS), None).extract(
        lines, state_code="MH", declared_on=date(2026, 9, 25), order_ref="GR", source_url=None)
    assert [(r["taluka"], r["area_id"]) for r in result.accepted] == [("Mohol", 1)]  # Solapur's, not Elsewhere's


GR_TABLE = [
    "मंत्रालय, मुंबई ४०० ०३२",                          # letterhead: must never become a taluka
    "सन २०२6 च्या खरीप हंगामातील 265 तालुकयांमध्ये दुष्काळ जाहीर करुन",
    "दिनांक : २५ सप्टेंबर, २०२6",
    "महसलू निभाग अ.क्र. निल्ह ा",                        # table header (serial-number column)
    "तालकु याांची नािे तालकु याांची सांख्या",
    "बीड ,गेवराई, माजलगाव,",
    "18 बीड परळी, आष्टी, पाटोदा, 6",                     # row number + district + first name, no comma
    "एकूर् तालकु े 265",                                 # total line ends the table
    "मुंबई येथे दिनांक",                                  # after the table: ignored
]
TABLE_TALUKAS = [(21, "Beed", "Beed"), (22, "Georai", "Beed"), (23, "Majalgaon", "Beed"), (24, "Parli", "Beed"),
                 (25, "Ashti", "Beed"), (26, "Patoda", "Beed"), (27, "Mumbai", "Mumbai City"),
                 (28, "Satara", "Satara"), (29, "Baramati", "Pune")]


def test_only_the_annex_table_is_read_and_row_lines_are_split_into_names():
    result = DeclarationExtractor(TalukaMatcher(TABLE_TALUKAS), None).extract(
        GR_TABLE, state_code="MH", declared_on=date(2026, 9, 26), order_ref="GR", source_url=None)
    assert {r["taluka"] for r in result.accepted} == {"Beed", "Georai", "Majalgaon", "Parli", "Ashti", "Patoda"}
    assert result.check == []  # no prose words ("सप्टेंबर", the letterhead) reach the check list


GR_DIVISIONS = [
    "महसलू निभाग अ.क्र. निल्ह ा",
    "1 ठाणे निरंक 0",                                   # district cell of a row with no talukas
    "ठाणे",                                             # revenue-division label in the first column
    "मालेगाव, िांदगाव,",
    "6 िानिक 2",                                        # district cell (Nashik): Nashik taluka is NOT declared
    "नानशक चाळीसगाव, सातारा",                           # division label joined to the first name
    "धाराशिव, कळंब",                                    # Dharashiv is the new official name of Osmanabad
    "शासन ननर्णय, क्रमाांक:- सनमती-2026/प्र.क्र.82/मदत-2",   # page header repeated on every annex page
    "खिीप हांगाम-2026 -प्रथम कळ (Trigger-1) लाग ु झालेल्या तालकु याांची माहीती",
    "4 रत्िानगरी रत्िानगरी,संगमेश्वर 2",                  # district cell, then the same name as a taluka
    "घिसावंगी अंबड , जालिा परतूर,मंठा",                   # a namesake later in the list (missing comma)
    "एकूर् तालकु े 5",
]
DIVISION_TALUKAS = [(31, "Thane", "Thane"), (32, "Malegaon", "Nashik"), (33, "Nandgaon", "Nashik"),
                    (34, "Nashik", "Nashik"), (35, "Chalisgaon", "Jalgaon"), (36, "Satara", "Satara"),
                    (37, "Osmanabad", "Osmanabad"), (38, "Kalamb", "Osmanabad"), (39, "Ratnagiri", "Ratnagiri"),
                    (40, "Sangameshwar", "Ratnagiri"), (41, "Jalna", "Jalna"), (42, "Partur", "Jalna"),
                    (43, "Ghansawangi", "Jalna"), (44, "Ambad", "Jalna"), (45, "Mantha", "Jalna"),
                    (46, "Kagal", "Kolhapur"), (47, "Tala", "Raigarh")]


def test_district_and_division_cells_never_auto_accept_their_namesake_taluka():
    result = DeclarationExtractor(TalukaMatcher(DIVISION_TALUKAS), None).extract(
        GR_DIVISIONS, state_code="MH", declared_on=date(2026, 9, 26), order_ref="GR", source_url=None)
    assert {r["taluka"] for r in result.accepted} == {"Malegaon", "Nandgaon", "Chalisgaon", "Satara",
                                                       "Osmanabad", "Kalamb", "Ratnagiri", "Sangameshwar", "Jalna",
                                                       "Partur", "Ghansawangi", "Ambad", "Mantha"}
    assert result.check == []  # district columns and page headers are not talukas: nothing for a person to check


GR_SAME_NAMES = [
    "महसलू निभाग अ.क्र. निल्ह ा",
    "मालेगाव, बागलाण, कळवण,",                           # Malegaon exists in Nashik and Washim: neighbours say Nashik
    "6 नाशिक 3",
    "वर्धा, सेलू, देवळी,",
    "29 वर्धा 4",
    "आष्टी",                                            # Ashti exists in Beed and Wardha: lines around say Wardha
    "एकूर् तालकु े 7",
]
SAME_NAME_TALUKAS = [(51, "Malegaon", "Nashik"), (52, "Malegaon", "Washim"), (53, "Baglan", "Nashik"),
                     (54, "Kalwan", "Nashik"), (55, "Wardha", "Wardha"), (56, "Selu", "Wardha"),
                     (57, "Selu", "Parbhani"), (58, "Deoli", "Wardha"), (59, "Ashti", "Bid"), (60, "Ashti", "Wardha")]


def test_a_name_found_in_two_districts_is_settled_by_its_neighbours():
    result = DeclarationExtractor(TalukaMatcher(SAME_NAME_TALUKAS), None).extract(
        GR_SAME_NAMES, state_code="MH", declared_on=date(2026, 9, 26), order_ref="GR", source_url=None)
    assert sorted(r["area_id"] for r in result.accepted) == [51, 53, 54, 55, 56, 58, 60]
    assert result.check == []
