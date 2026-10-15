"""Load and validate config/config.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"

REQUIRED_KEYS = (
    "gee_project", "drive_folder", "aoi_bbox", "smoke_bbox", "year", "crs", "scale",
    "datasets", "assets", "bands", "cs_cdf_threshold", "nodata",
    "patch_size", "block_size_m", "split_ratios", "seed", "lambdas",
    "agc_fraction", "peat_cd_kgc_m3", "temporary_labels", "peat_ignore_index", "peat_classes",
)
SPLITS = ("train", "val", "test")
TASKS = ("height", "agb", "peat")


def is_todo(value: Any) -> bool:
    """True for placeholders that still have to be filled in: None, '' or 'TODO'."""
    return value is None or (isinstance(value, str) and value.strip().upper() in ("", "TODO"))


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Read the YAML config and check it with validate()."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    validate(cfg)
    return cfg


def validate(cfg: dict[str, Any]) -> None:
    """Raise ValueError if the config breaks an invariant the pipeline relies on."""
    missing = [key for key in REQUIRED_KEYS if key not in cfg]
    if missing:
        raise ValueError(f"config is missing keys: {missing}")

    _check_bbox("aoi_bbox", cfg["aoi_bbox"])
    _check_bbox("smoke_bbox", cfg["smoke_bbox"])
    aoi, smoke = cfg["aoi_bbox"], cfg["smoke_bbox"]
    if not (aoi[0] <= smoke[0] and aoi[1] <= smoke[1] and smoke[2] <= aoi[2] and smoke[3] <= aoi[3]):
        raise ValueError("smoke_bbox must lie inside aoi_bbox")

    if not str(cfg["crs"]).startswith("EPSG:"):
        raise ValueError(f"crs must look like 'EPSG:<code>', got {cfg['crs']!r}")

    bands = cfg["bands"]
    if not bands or len(set(bands)) != len(bands):
        raise ValueError("bands must be a non-empty list without duplicates")

    # A patch that straddles two blocks is dropped from the split, so blocks must tile into whole patches.
    patch_m = cfg["patch_size"] * cfg["scale"]
    if cfg["block_size_m"] % patch_m:
        raise ValueError(
            f"block_size_m ({cfg['block_size_m']}) must be a multiple of patch_size * scale ({patch_m} m)"
        )

    ratios = cfg["split_ratios"]
    if sorted(ratios) != sorted(SPLITS) or abs(sum(ratios.values()) - 1.0) > 1e-6:
        raise ValueError(f"split_ratios must give train/val/test summing to 1, got {ratios}")

    if sorted(cfg["lambdas"]) != sorted(TASKS):
        raise ValueError(f"lambdas must have exactly the keys {TASKS}, got {sorted(cfg['lambdas'])}")

    _check_peat_classes(cfg["peat_classes"], cfg["peat_ignore_index"])


def _check_bbox(name: str, bbox: list[float]) -> None:
    if len(bbox) != 4:
        raise ValueError(f"{name} must be [lon_min, lat_min, lon_max, lat_max], got {bbox}")
    lon_min, lat_min, lon_max, lat_max = bbox
    if not (-180 <= lon_min < lon_max <= 180 and -90 <= lat_min < lat_max <= 90):
        raise ValueError(f"{name} is not a valid lon/lat box: {bbox}")


def _check_peat_classes(classes: dict[int, dict[str, Any]], ignore_index: int) -> None:
    codes = list(classes)
    if codes != list(range(len(codes))):
        raise ValueError(f"peat_classes codes must be 0..K-1 in order, got {codes}")
    if ignore_index in classes:
        raise ValueError(f"peat_ignore_index {ignore_index} collides with a class code")

    for code, cls in classes.items():
        last = code == codes[-1]
        if cls["max_cm"] is None and not last:
            raise ValueError(f"only the last peat class may be open-ended (class {code})")
        if cls["max_cm"] is not None and cls["min_cm"] >= cls["max_cm"]:
            raise ValueError(f"peat class {code}: min_cm must be below max_cm")
        if not last and cls["max_cm"] != classes[code + 1]["min_cm"]:
            raise ValueError(f"peat classes {code} and {code + 1} leave a gap or overlap")
        depth = cls["depth_m"]
        if not depth["low"] <= depth["mid"] <= depth["high"]:
            raise ValueError(f"peat class {code}: depth_m must satisfy low <= mid <= high")
