import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

from app.integrations.population import WorldPopGrid
from app.integrations.raster import Grid, coverage_sum, read_window, resample_nearest, zonal_mean, zonal_sums


def write_tif(path, values, transform, nodata=None):
    with rasterio.open(path, "w", driver="GTiff", width=values.shape[1], height=values.shape[0], count=1,
                       dtype="float32", crs="EPSG:4326", transform=transform, nodata=nodata) as dst:
        dst.write(values.astype("float32"), 1)


def grid_1deg():
    """10x10 one-degree pixels from lon 70..80, lat 30..20; value = row*10 + col."""
    return Grid(np.arange(100, dtype=float).reshape(10, 10), from_origin(70, 30, 1, 1))


def test_read_window_crops_and_masks_nodata(tmp_path):
    values = np.arange(100, dtype=float).reshape(10, 10)
    values[0, 0] = -99999
    write_tif(tmp_path / "g.tif", values, from_origin(70, 30, 1, 1), nodata=-99999)
    with rasterio.open(tmp_path / "g.tif") as src:
        g = read_window(src, (70, 27, 73, 30))  # 3x3 top-left block
    assert g.values.shape == (3, 3) and np.isnan(g.values[0, 0]) and g.values[2, 2] == 22


def test_coverage_sum_is_exact_on_whole_pixels_and_fractional_on_partial_ones():
    g = grid_1deg()
    assert coverage_sum(g, box(70, 28, 72, 30)) == pytest.approx(0 + 1 + 10 + 11)
    assert coverage_sum(g, box(75, 25, 75.5, 26)) == pytest.approx(0.5 * 45, rel=0.05)  # half of pixel (4,5)
    assert coverage_sum(g, box(100, 0, 101, 1)) == 0  # outside the grid


def test_zonal_mean_uses_pixel_centres_and_falls_back_to_a_point_for_tiny_shapes():
    g = grid_1deg()
    means = zonal_mean(g, [(7, box(70, 28, 72, 30)), (9, Point(75.5, 25.5).buffer(0.1))])
    assert means[7] == pytest.approx((0 + 1 + 10 + 11) / 4)
    assert means[9] == 45  # covers no pixel centre: value of the pixel under its interior point


def test_zonal_mean_skips_shapes_over_nodata_only():
    g = grid_1deg()
    g.values[:, :] = np.nan
    assert zonal_mean(g, [(1, box(70, 28, 72, 30))]) == {}


def test_zonal_sums_add_values_per_shape_with_an_optional_mask():
    g = grid_1deg()
    mask = g.values >= 11
    sums = zonal_sums(g, [(1, box(70, 28, 72, 30)), (2, box(78, 20, 80, 22))], mask=mask)
    assert sums[1] == pytest.approx(11) and sums[2] == pytest.approx(88 + 89 + 98 + 99)


def test_resample_nearest_maps_a_coarse_grid_onto_a_fine_one():
    coarse = Grid(np.array([[1.0, 2.0], [3.0, 4.0]]), from_origin(70, 30, 5, 5))
    fine = resample_nearest(coarse, from_origin(70, 30, 2.5, 2.5), (4, 4))
    assert fine[0, 0] == 1 and fine[0, 3] == 2 and fine[3, 0] == 3 and fine[3, 3] == 4


def test_worldpop_counts_people_and_splits_urban_by_density(tmp_path):
    # 0.01 deg pixels (~1.2 km2 near 20N): 5,000 people is urban (>1,500/km2), 100 is rural
    values = np.full((10, 10), 100.0)
    values[:5, :5] = 5000.0
    write_tif(tmp_path / "pop.tif", values, from_origin(70, 20.1, 0.01, 0.01), nodata=-99999)
    grid = WorldPopGrid(tmp_path / "pop.tif")
    whole = grid.count(box(70, 20.0, 70.1, 20.1).wkt)
    assert whole.total == pytest.approx(25 * 5000 + 75 * 100, rel=0.01)
    assert whole.urban == pytest.approx(25 * 5000, rel=0.01)
    rural_corner = grid.count(box(70.05, 20.0, 70.1, 20.05).wkt)
    assert rural_corner.urban == 0 and rural_corner.total == pytest.approx(25 * 100, rel=0.01)


def test_missing_population_file_fails_soft(tmp_path):
    assert WorldPopGrid(tmp_path / "nope.tif").count(box(70, 20, 71, 21).wkt) is None
