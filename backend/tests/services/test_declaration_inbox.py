import os
from datetime import date

from app.services.declaration_inbox import DeclarationInbox, order_from_filename

TALUKAS = [(1, "Mohol", "Solapur"), (2, "Akkalkot", "Solapur"), (3, "Barshi", "Solapur")]
DROUGHT_GR = ["महाराष्ट्र शासन, मदत व पुनर्वसन विभाग", "राज्यातील तालुक्यांमध्ये दुष्काळ जाहीर करण्याबाबत",
              "जिल्हा : सोलापूर", "१. मोहोळ   २. अक्कलकोट   ३. बार्शी"]
OTHER_GR = ["कौशल्य विकास विभाग", "स्टार्टअप धोरण-२०२५ बाबत"]


def make_inbox(tmp_path, texts: dict[str, list[str]]):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for name in texts:
        (inbox / name).write_bytes(b"%PDF-1.4 test")
    return DeclarationInbox(inbox, tmp_path / "out", read_lines=lambda p: texts[p.name], talukas_for=lambda s: TALUKAS)


def test_official_file_names_give_the_order_date_and_number():
    assert order_from_filename("202609251512341234.pdf") == (date(2026, 9, 25), "GR 202609251512341234")
    assert order_from_filename("drought order.pdf") is None


def test_drought_orders_become_csv_files_and_move_to_processed(tmp_path):
    box = make_inbox(tmp_path, {"202609251512341234.pdf": DROUGHT_GR, "202610091708267603.pdf": OTHER_GR})
    results = {r.file: r for r in box.process(state="MH")}
    drought = results["202609251512341234.pdf"]
    assert drought.status == "extracted" and drought.accepted == 3 and drought.csv.exists()
    assert drought.declared_on == date(2026, 9, 25)
    assert results["202610091708267603.pdf"].status == "not a drought order"
    assert (tmp_path / "inbox" / "processed" / "202609251512341234.pdf").exists()
    assert (tmp_path / "inbox" / "skipped" / "202610091708267603.pdf").exists()
    assert box.process(state="MH") == []  # nothing left to do: files are never read twice


def test_a_hand_named_file_uses_its_saved_date(tmp_path):
    box = make_inbox(tmp_path, {"order.pdf": DROUGHT_GR})
    saved = date(2026, 9, 26)
    os.utime(tmp_path / "inbox" / "order.pdf", (0, int(__import__("datetime").datetime(2026, 9, 26, 12).timestamp())))
    [result] = box.process(state="MH")
    assert result.declared_on == saved and result.order_ref == "order.pdf (date from file)"


def test_the_command_loads_accepted_talukas_into_the_database(db, tmp_path):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import box

    from app.cli.process_declaration_inbox import run
    from app.models import AdminArea, DroughtDeclaration
    for i, name in enumerate(("Mohol", "Akkalkot", "Barshi")):
        db.add(AdminArea(level="subdistrict", name=name, name_norm=name.lower(), state_code="MH",
                         district_name="Solapur", geom=from_shape(box(75 + i, 17, 75.5 + i, 17.5), srid=4326)))
    db.flush()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "202609251512341234.pdf").write_bytes(b"%PDF-1.4")
    loaded = run(db, inbox, tmp_path / "out", read_lines=lambda p: DROUGHT_GR, translator=None)
    assert loaded == 3
    rows = db.query(DroughtDeclaration).all()
    assert len(rows) == 3 and {r.declared_on for r in rows} == {date(2026, 9, 25)}
