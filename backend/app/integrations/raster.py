"""Small raster toolkit shared by the population grid and the drought data sources.

Everything works on a `Grid` (a 2-D float array, NaN = no data, plus its affine transform in lon/lat degrees).
We only need sums and means over polygons, so this stays tiny instead of pulling in a zonal-stats library.
"""
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from affine import Affine
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry.base import BaseGeometry

FINE = 10  # sub-pixel factor for fractional coverage of small shapes


@dataclass
class Grid:
    values: np.ndarray  # float, NaN where there is no data
    transform: Affine

    @property
    def shape(self) -> tuple[int, int]:
        return self.values.shape

    def window_of(self, bounds: tuple[float, float, float, float]) -> tuple[slice, slice] | None:
        """Row/column slices covering lon/lat bounds, clipped to the grid (None if outside)."""
        west, south, east, north = bounds
        inverse = ~self.transform
        c_a, r_a = inverse @ (west, north)
        c_b, r_b = inverse @ (east, south)
        r0, r1 = sorted((r_a, r_b))
        c0, c1 = sorted((c_a, c_b))
        r0, c0 = max(0, int(np.floor(r0))), max(0, int(np.floor(c0)))
        r1, c1 = min(self.shape[0], int(np.ceil(r1))), min(self.shape[1], int(np.ceil(c1)))
        return (slice(r0, r1), slice(c0, c1)) if r0 < r1 and c0 < c1 else None


def read_window(src, bounds: tuple[float, float, float, float]) -> Grid:
    """Read one band of an open rasterio dataset inside lon/lat bounds; nodata becomes NaN."""
    win: Window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
    band = src.read(1, window=win, masked=True, boundless=False)
    values = band.astype("float64").filled(np.nan)
    return Grid(values, src.window_transform(win))


def _labels(grid: Grid, shapes: list[tuple[int, BaseGeometry]]) -> np.ndarray:
    """Pixel -> 1-based index into `shapes` (0 = none), judged by pixel centre."""
    return rasterize(((geom, i + 1) for i, (_, geom) in enumerate(shapes)), out_shape=grid.shape,
                     transform=grid.transform, fill=0, dtype="int32")


def zonal_mean(grid: Grid, shapes: list[tuple[int, BaseGeometry]]) -> dict[int, float]:
    """Mean value per shape id. Shapes too small to contain a pixel centre take the value under their
    interior point, so small urban talukas still get a reading from a coarse (e.g. 5 km) grid."""
    if not shapes:
        return {}
    labels = _labels(grid, shapes)
    valid = ~np.isnan(grid.values)
    n = len(shapes) + 1
    sums = np.bincount(labels[valid], weights=grid.values[valid], minlength=n)
    counts = np.bincount(labels[valid], minlength=n)
    covered = np.bincount(labels.ravel(), minlength=n)
    out: dict[int, float] = {}
    inverse = ~grid.transform
    for i, (area_id, geom) in enumerate(shapes, start=1):
        if counts[i]:
            out[area_id] = float(sums[i] / counts[i])
        elif not covered[i]:  # no pixel centre inside: sample at an interior point
            p = geom.representative_point()
            col, row = (int(v) for v in inverse @ (p.x, p.y))
            if 0 <= row < grid.shape[0] and 0 <= col < grid.shape[1] and not np.isnan(grid.values[row, col]):
                out[area_id] = float(grid.values[row, col])
    return out


def zonal_sums(grid: Grid, shapes: list[tuple[int, BaseGeometry]], mask: np.ndarray | None = None) -> dict[int, float]:
    """Sum of values per shape id (pixel-centre rule), optionally only where `mask` is true."""
    if not shapes:
        return {}
    labels = _labels(grid, shapes)
    keep = ~np.isnan(grid.values) if mask is None else (~np.isnan(grid.values) & mask)
    sums = np.bincount(labels[keep], weights=grid.values[keep], minlength=len(shapes) + 1)
    return {area_id: float(sums[i]) for i, (area_id, _) in enumerate(shapes, start=1)}


def coverage_sum(grid: Grid, geom: BaseGeometry, mask: np.ndarray | None = None) -> float:
    """Sum of values weighted by the fraction of each pixel the shape covers (exact enough at 1/10 pixel).
    Used for zone populations, where zones can be smaller than one pixel."""
    window = grid.window_of(geom.bounds)
    if window is None:
        return 0.0
    rows, cols = window
    sub = grid.values[rows, cols]
    h, w = sub.shape
    origin = grid.transform @ Affine.translation(cols.start, rows.start)
    fine = rasterize([(geom, 1)], out_shape=(h * FINE, w * FINE), transform=origin @ Affine.scale(1 / FINE),
                     fill=0, dtype="uint8")
    fraction = fine.reshape(h, FINE, w, FINE).mean(axis=(1, 3))
    weights = fraction if mask is None else fraction * mask[rows, cols]
    return float(np.nansum(sub * weights))


def resample_nearest(grid: Grid, transform: Affine, shape: tuple[int, int]) -> np.ndarray:
    """Values of `grid` at the pixel centres of another grid (nearest neighbour); NaN outside."""
    # both grids are north-up and axis-aligned: map row and column centres separately (1-D), then gather once
    # (a full 2-D coordinate mesh of the 1 km India grid would cost ~1 GB)
    xs = transform.c + (np.arange(shape[1]) + 0.5) * transform.a
    ys = transform.f + (np.arange(shape[0]) + 0.5) * transform.e
    src_cols = np.floor((xs - grid.transform.c) / grid.transform.a).astype(int)
    src_rows = np.floor((ys - grid.transform.f) / grid.transform.e).astype(int)
    ok_r = (src_rows >= 0) & (src_rows < grid.shape[0])
    ok_c = (src_cols >= 0) & (src_cols < grid.shape[1])
    out = np.full(shape, np.nan)
    out[np.ix_(ok_r, ok_c)] = grid.values[np.ix_(src_rows[ok_r], src_cols[ok_c])]
    return out


def shapes_from_wkb(rows: Iterable[tuple[int, bytes]]) -> list[tuple[int, BaseGeometry]]:
    from shapely import wkb
    return [(area_id, wkb.loads(bytes(blob))) for area_id, blob in rows]


INDIA_BOUNDS = (68.0, 6.0, 98.0, 38.0)  # lon/lat window read from global rasters


def fetch_window(http, url: str, bounds: tuple[float, float, float, float], service: str) -> Grid:
    """Download a GeoTIFF to a temporary file, read one window, delete the file.

    Simpler and sturdier than HTTP range reads across differently laid-out files; India-sized windows of the
    global drought rasters cost ~70-90 MB per download, a few times a month.
    """
    import tempfile
    from pathlib import Path

    import httpx
    import rasterio

    from app.core.exceptions import ExternalServiceError

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "raster.tif"
        try:
            with http.stream("GET", url, timeout=300) as res:
                if res.status_code >= 400:
                    raise ExternalServiceError(service, f"HTTP {res.status_code}",
                                               retryable=res.status_code >= 500 or res.status_code == 429)
                with path.open("wb") as fh:
                    for chunk in res.iter_bytes():
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(service, f"download failed ({type(exc).__name__})") from None
        try:
            with rasterio.open(path) as src:
                return read_window(src, bounds)
        except rasterio.errors.RasterioIOError:
            raise ExternalServiceError(service, "downloaded file is not a readable raster", retryable=False) from None
