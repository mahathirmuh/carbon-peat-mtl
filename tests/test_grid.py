import pytest
from rasterio.warp import transform_bounds

from src.config import DEFAULT_CONFIG, load_config
from src.grid import working_grid


@pytest.fixture
def cfg():
    return load_config(DEFAULT_CONFIG)


@pytest.mark.parametrize("box", ["aoi_bbox", "smoke_bbox"])
def test_grid_edges_on_pixel_multiples(cfg, box):
    grid = working_grid(cfg, cfg[box])
    assert grid.x0 % cfg["scale"] == 0
    assert grid.y0 % cfg["scale"] == 0
    assert grid.transform == [cfg["scale"], 0, grid.x0, 0, -cfg["scale"], grid.y0]


@pytest.mark.parametrize("box", ["aoi_bbox", "smoke_bbox"])
def test_grid_covers_bbox(cfg, box):
    grid = working_grid(cfg, cfg[box])
    left, bottom, right, top = transform_bounds("EPSG:4326", cfg["crs"], *cfg[box])
    g_left, g_bottom, g_right, g_top = grid.bounds
    assert g_left <= left and g_bottom <= bottom and g_right >= right and g_top >= top
    # and it is tight: less than one pixel of slack on every side
    assert left - g_left < grid.scale and bottom - g_bottom < grid.scale
    assert g_right - right < grid.scale and g_top - top < grid.scale


def test_smoke_grid_is_inside_aoi_grid(cfg):
    aoi = working_grid(cfg, cfg["aoi_bbox"])
    smoke = working_grid(cfg, cfg["smoke_bbox"])
    assert aoi.x0 <= smoke.x0 and smoke.y0 <= aoi.y0
    assert smoke.bounds[2] <= aoi.bounds[2] and smoke.bounds[1] >= aoi.bounds[1]
