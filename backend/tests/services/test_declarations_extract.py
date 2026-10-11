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


def test_without_a_translator_names_still_match_and_severity_needs_checking():
    result = extract(None)
    assert {r["taluka"] for r in result.accepted} == {"Mohol", "Akkalkot", "Barshi"}
    assert all(r["severity"] == "unknown" for r in result.accepted)


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
