"""People counts from the WorldPop 2025 ~1 km population grid (CC BY 4.0)."""
import logging
from functools import cached_property
from pathlib import Path

import numpy as np
import rasterio
from shapely import wkt as shapely_wkt

from app.integrations.ports import PopulationCount
from app.integrations.raster import Grid, coverage_sum

LOG = logging.getLogger(__name__)
KM_PER_DEGREE = 111.32


class WorldPopGrid:
    """Counts people inside any polygon, split urban/rural by density.

    Loads the whole India raster once (~50 MB in memory). A missing file returns None, so callers fall
    back to gazetteer populations instead of failing.
    ponytail: "urban" = pixel density >= 1,500 people/km2; the full GHSL degree-of-urbanisation rule
    (contiguous clusters of 50k+) is the upgrade if the split needs to be exact.
    """

    def __init__(self, path: Path | str, urban_density: float = 1500.0):
        self.path = Path(path)
        self.urban_density = urban_density

    @cached_property
    def grid(self) -> Grid | None:
        if not self.path.exists():
            LOG.warning("population grid %s not found; zone populations fall back to the gazetteer", self.path)
            return None
        with rasterio.open(self.path) as src:
            values = src.read(1, masked=True).astype("float64").filled(np.nan)
            return Grid(values, src.transform)

    @cached_property
    def urban_mask(self) -> np.ndarray | None:
        g = self.grid
        if g is None:
            return None
        rows = np.arange(g.shape[0])
        lat = (g.transform @ (np.zeros_like(rows) + 0.5, rows + 0.5))[1]
        pixel_km2 = (abs(g.transform.a) * KM_PER_DEGREE) * (abs(g.transform.e) * KM_PER_DEGREE) \
            * np.cos(np.radians(lat))
        density = g.values / pixel_km2[:, None]
        return np.nan_to_num(density) >= self.urban_density

    def count(self, wkt: str) -> PopulationCount | None:
        if self.grid is None:
            return None
        geom = shapely_wkt.loads(wkt)
        total = coverage_sum(self.grid, geom)
        urban = coverage_sum(self.grid, geom, mask=self.urban_mask)
        return PopulationCount(total=int(round(total)), urban=int(round(urban)))
