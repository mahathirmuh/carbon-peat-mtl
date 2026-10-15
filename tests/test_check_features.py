import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from scripts.check_features import band_stats, check_grid, write_tags
from src.grid import Grid

BANDS = ["a", "b"]
NODATA = -9999.0
GRID = Grid("EPSG:32749", x0=1000, y0=2000, scale=10, width=4, height=3)


def write_tif(path, x0=1000, y0=2000, width=4, height=3, count=2):
    data = np.arange(count * height * width, dtype="float32").reshape(count, height, width)
    data[1, 0, 0] = NODATA
    with rasterio.open(path, "w", driver="GTiff", width=width, height=height, count=count, dtype="float32",
                       crs="EPSG:32749", transform=Affine(10, 0, x0, 0, -10, y0)) as ds:
        ds.write(data)
    return data


def test_matching_tile_has_no_problems(tmp_path):
    path = tmp_path / "f.tif"
    write_tif(path)
    assert check_grid([path], GRID, BANDS) == []


@pytest.mark.parametrize("kwargs, message", [
    ({"x0": 1005}, "not inside the working grid"),
    ({"count": 3}, "3 bands"),
    ({"width": 2}, "tiles cover"),
])
def test_bad_tiles_are_reported(tmp_path, kwargs, message):
    path = tmp_path / "f.tif"
    write_tif(path, **kwargs)
    assert any(message in p for p in check_grid([path], GRID, BANDS))


def test_write_tags_sets_nodata_and_band_names(tmp_path):
    path = tmp_path / "f.tif"
    write_tif(path)
    write_tags(path, BANDS, NODATA)
    with rasterio.open(path) as ds:
        assert ds.nodata == NODATA
        assert list(ds.descriptions) == BANDS
    assert check_grid([path], GRID, BANDS) == []


def test_band_stats_skip_nodata(tmp_path):
    path = tmp_path / "f.tif"
    data = write_tif(path)
    stats = band_stats([path], BANDS, NODATA)
    assert stats["a"]["valid_fraction"] == 1.0
    assert stats["a"]["mean"] == pytest.approx(data[0].mean())
    valid_b = data[1][data[1] != NODATA]
    assert stats["b"]["valid_fraction"] == pytest.approx(11 / 12, abs=1e-6)
    assert stats["b"]["min"] == valid_b.min()
    assert stats["b"]["std"] == pytest.approx(valid_b.std(), rel=1e-6)
