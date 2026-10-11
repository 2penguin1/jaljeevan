import io
from datetime import date

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.core.exceptions import ExternalServiceError
from app.integrations.chirps import ChirpsSpiSource
from app.integrations.soil import GdoSoilMoistureAnomaly

CHIRPS_LISTING = """<html><a href="SPI_18PentAccum_2026_p54_PRELIM.tif">x</a>
<a href="SPI_18PentAccum_2026_p55_PRELIM.tif">x</a><a href="SPI_18PentAccum_2026_p55_PRELIM_data_used.txt">x</a>
<a href="SPI_18PentAccum_2025_p72_PRELIM.tif">x</a></html>"""
GDO_LISTING = """<a href="smang_m_gdo_20260901_t_300_z01.tif">a</a> <a href="smang_m_gdo_20260911_t_300_z01.tif">b</a>"""


def tif_bytes(value=-1.5) -> bytes:
    """A 'global-ish' 1-degree raster covering 60..100E, 0..40N."""
    data = np.full((40, 40), value, dtype="float32")
    data[0, 0] = np.nan
    buf = io.BytesIO()
    with rasterio.MemoryFile() as mem:
        with mem.open(driver="GTiff", width=40, height=40, count=1, dtype="float32", crs="EPSG:4326",
                      transform=from_origin(60, 40, 1, 1)) as dst:
            dst.write(data, 1)
        buf.write(mem.read())
    return buf.getvalue()


def client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        for suffix, response in routes.items():
            if str(request.url).endswith(suffix):
                return response
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_chirps_finds_the_newest_pentad_and_reads_only_india():
    http = client({"/18_pentad/prelim/": httpx.Response(200, text=CHIRPS_LISTING),
                   "SPI_18PentAccum_2026_p55_PRELIM.tif": httpx.Response(200, content=tif_bytes(-2.0))})
    src = ChirpsSpiSource(http, "https://chc.test/SPI/CHIRPS3")
    assert src.latest("18") == (2026, 55)
    grid = src.fetch("18", 2026, 55)
    assert grid.values.shape == (32, 30)  # 68..98E x 6..38N at 1 degree
    assert np.nanmax(grid.values) == pytest.approx(-2.0)


def test_chirps_failures_become_external_service_errors():
    src = ChirpsSpiSource(client({"/18_pentad/prelim/": httpx.Response(503)}), "https://chc.test/SPI/CHIRPS3")
    with pytest.raises(ExternalServiceError):
        src.latest("18")
    empty = ChirpsSpiSource(client({"/06_pentad/prelim/": httpx.Response(200, text="<html></html>")}),
                            "https://chc.test/SPI/CHIRPS3")
    assert empty.latest("06") is None


def test_gdo_soil_finds_the_newest_dekad_and_reads_india():
    http = client({"/ver3-0-1/": httpx.Response(200, text=GDO_LISTING),
                   "smang_m_gdo_20260911_t_300_z01.tif": httpx.Response(200, content=tif_bytes(-1.2))})
    src = GdoSoilMoistureAnomaly(http, "https://gdo.test/ver3-0-1/")
    assert src.latest() == date(2026, 9, 11)
    assert np.nanmin(src.fetch(date(2026, 9, 11)).values) == pytest.approx(-1.2)
