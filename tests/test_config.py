import pytest

from src.config import DEFAULT_CONFIG, is_todo, load_config, validate

# Order from CLAUDE.md, "Stack input: 19 kanal (urutan tetap)".
EXPECTED_BANDS = [
    "B2", "B3", "B4", "B8", "B11", "B12",
    "NDVI", "EVI",
    "B8_contrast", "B8_ent", "B8_var",
    "VV", "VH", "VH_minus_VV",
    "HH_dB", "HV_dB",
    "elevation", "elevation_lowpass", "slope",
]


@pytest.fixture
def cfg():
    return load_config(DEFAULT_CONFIG)


def test_band_order_is_fixed(cfg):
    assert cfg["bands"] == EXPECTED_BANDS


def test_blocks_align_with_patches(cfg):
    assert cfg["block_size_m"] % (cfg["patch_size"] * cfg["scale"]) == 0


def test_rejects_block_not_aligned_with_patches(cfg):
    cfg["block_size_m"] = 5000
    with pytest.raises(ValueError, match="block_size_m"):
        validate(cfg)


def test_rejects_export_tile_not_multiple_of_256(cfg):
    cfg["export_tile_px"] = 4000
    with pytest.raises(ValueError, match="export_tile_px"):
        validate(cfg)


def test_rejects_split_ratios_not_summing_to_one(cfg):
    cfg["split_ratios"]["test"] = 0.25
    with pytest.raises(ValueError, match="split_ratios"):
        validate(cfg)


def test_rejects_gap_between_peat_classes(cfg):
    cfg["peat_classes"][2]["min_cm"] = 120
    with pytest.raises(ValueError, match="gap or overlap"):
        validate(cfg)


def test_rejects_smoke_window_outside_aoi(cfg):
    cfg["smoke_bbox"] = [113.4, -2.4, 113.6, -2.2]
    with pytest.raises(ValueError, match="smoke_bbox"):
        validate(cfg)


@pytest.mark.parametrize(
    "value, expected",
    [("TODO", True), (" todo ", True), ("", True), (None, True), ("my-gee-project", False)],
)
def test_is_todo(value, expected):
    assert is_todo(value) is expected
