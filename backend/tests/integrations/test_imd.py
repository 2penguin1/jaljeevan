import httpx

from app.integrations.imd import ImdDistrictRainfall

PAGE = r'''<script> var map = { "areas": [
    {
        "title": "SOLAPUR",
        "id": "300",
        "color": "#F94112",
        "info": "-45%",
        "balloonText": "<h6>SOLAPUR<\/h6> <p><em>Date : 2026-10-10<\/br>Departure : -45%<\/br>Actual : 20 mm<\/br>Normal : 36 mm<\/em><\/p>"
    },
    {
        "title": "AURANGABAD",
        "id": "301",
        "info": "12%",
        "balloonText": "<h6>AURANGABAD<\/h6> <p><em>Date : 2026-10-10<\/br>Departure : 12%<\/em><\/p>"
    },
    {
        "title": "NO DATA",
        "id": "302",
        "info": "NR",
        "balloonText": "<h6>NO DATA<\/h6>"
    }
] } </script>'''


def source(response: httpx.Response) -> ImdDistrictRainfall:
    return ImdDistrictRainfall(httpx.Client(transport=httpx.MockTransport(lambda r: response)))


def test_parses_district_departures_and_skips_unreadable_entries():
    readings = ImdDistrictRainfall.parse(PAGE)
    assert [(r.district, r.departure_pct, r.day.isoformat()) for r in readings] == [
        ("SOLAPUR", -45.0, "2026-10-10"), ("AURANGABAD", 12.0, "2026-10-10")]


def test_fetch_fails_soft():
    assert source(httpx.Response(500)).fetch() == []
    assert source(httpx.Response(200, text="<html>layout changed</html>")).fetch() == []
    assert len(source(httpx.Response(200, text=PAGE)).fetch()) == 2
