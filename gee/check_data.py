"""Fase 1 data check: image counts, GEDI footprints, PEATGRIDS means, and quick-look PNGs.

Python port of gee/cek_data_gee.js (same filters, via gee/sources.py). Writes summary.json and the PNGs to
outputs/data_check/ for the full AOI, or to outputs/data_check/smoke/ for the smoke-test window.

Usage: python gee/check_data.py [--config config/config.yaml] [--region aoi|smoke] [--no-thumbs]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ee
import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets `python gee/check_data.py` import gee/ and src/ from the repo root

from gee import sources  # noqa: E402
from src.config import DEFAULT_CONFIG, is_todo, load_config  # noqa: E402

# gee/cek_data_gee.js on the full AOI for 2020 (CLAUDE.md, "Status", 15 Oct 2026), rounded as reported there.
REFERENCE_2020_AOI = {
    "s2_images": 365,
    "s2_composite_coverage": 0.999,
    "s1_images": 48,
    "palsar2_images": 1,
    "gedi_l4a_pixels": 111610,
    "gedi_l2a_pixels": 162131,
    "peatgrids_thickness_mean_cm": 275,
    "peatgrids_c_stock_mean_mgc_m2": 0.243,
}
THUMB_DIM = 1024  # longest side of the quick-look PNGs, in pixels
LAND_CELL_MIN = 0.5  # a grid cell counts as land when at least half of it is land (ESA WorldCover 2020)


def region_value(image: ee.Image, region: ee.Geometry, reducer: ee.Reducer, scale: float) -> ee.ComputedObject:
    """reduceRegion of a single-band image, returned as the bare value."""
    result = image.reduceRegion(reducer=reducer, geometry=region, scale=scale, maxPixels=1e10, tileScale=4)
    return result.values().get(0)


def compute_stats(cfg: dict, region: ee.Geometry) -> dict:
    """The numbers gee/cek_data_gee.js prints, computed with the same filters and scales."""
    s2_median = sources.s2_collection(cfg, region).median().clip(region)
    thick, c_stock = sources.peatgrids(cfg)
    queries = {
        "s2_images": sources.s2_collection(cfg, region).size(),
        "s2_composite_coverage": region_value(s2_median.select("B8").mask(), region, ee.Reducer.mean(), 100),
        "s1_images": sources.s1_collection(cfg, region).size(),
        "palsar2_images": sources.palsar2_collection(cfg, region).size(),
        "gedi_l4a_pixels": region_value(
            sources.gedi_mosaic(cfg, region, "gedi_l4a").clip(region), region, ee.Reducer.count(), 25),
        "gedi_l2a_pixels": region_value(
            sources.gedi_mosaic(cfg, region, "gedi_l2a").clip(region), region, ee.Reducer.count(), 25),
        "peatgrids_thickness_mean_cm": region_value(thick.clip(region), region, ee.Reducer.mean(), 1000),
        "peatgrids_c_stock_mean_mgc_m2": region_value(c_stock.clip(region), region, ee.Reducer.mean(), 1000),
        "land_fraction": region_value(sources.land_mask(cfg).clip(region), region, ee.Reducer.mean(), 100),
    }
    stats = {}
    for key, query in queries.items():  # one request each, like the separate print() calls in the JS
        t0 = time.time()
        stats[key] = query.getInfo()
        print(f"  {key:<30} {stats[key]}  ({time.time() - t0:.0f} s)")
    return stats


def count_distribution(counts: list[int]) -> dict:
    """Share of cells with at least one GEDI pixel, and percentiles of the per-cell count."""
    if not counts:
        return {"n_cells": 0}
    values = np.asarray(counts)
    p10, median, p90 = np.percentile(values, [10, 50, 90])
    return {
        "n_cells": int(values.size),
        "share_with_gedi": round(float((values > 0).mean()), 4),
        "p10": float(p10),
        "median": float(median),
        "p90": float(p90),
        "max": int(values.max()),
    }


def gedi_per_patch(cfg: dict, region: ee.Geometry, product: str = "gedi_l4a") -> dict:
    """GEDI pixels per patch-sized cell, to judge whether patches carry enough labels.

    Cells come from a grid in the working CRS (aligned to the CRS origin, not to the future patch grid) and
    only cells fully inside the region are counted. Sea cells can never hold GEDI land footprints, so the
    distribution is also reported for land cells only.
    """
    cell_m = cfg["patch_size"] * cfg["scale"]
    cells = region.coveringGrid(ee.Projection(cfg["crs"]), cell_m).filter(ee.Filter.isContained(".geo", region))
    cells = sources.land_mask(cfg).reduceRegions(
        collection=cells, reducer=ee.Reducer.mean().setOutputs(["land"]), scale=100)
    cells = sources.gedi_mosaic(cfg, region, product).reduceRegions(
        collection=cells, reducer=ee.Reducer.count(), scale=25, tileScale=4)
    t0 = time.time()
    rows = cells.reduceColumns(ee.Reducer.toList(2), ["count", "land"]).get("list").getInfo()
    stats = {
        "product": product,
        "cell_size_m": cell_m,
        "land_cell_min": LAND_CELL_MIN,
        "all_cells": count_distribution([int(count) for count, _ in rows]),
        "land_cells": count_distribution(
            [int(count) for count, land in rows if land is not None and land >= LAND_CELL_MIN]),
    }
    print(f"  {product}_per_patch  all {stats['all_cells']}")
    print(f"  {product}_per_patch  land {stats['land_cells']}  ({time.time() - t0:.0f} s)")
    return stats


def compare_to_reference(stats: dict, reference: dict) -> dict:
    """Relative difference (value - reference) / reference for every metric in the reference."""
    return {
        key: None if stats.get(key) is None else round((stats[key] - ref) / ref, 4)
        for key, ref in reference.items()
    }


def save_quicklooks(cfg: dict, region: ee.Geometry, out_dir: Path) -> list[str]:
    """Quick-look PNGs in the working CRS, with the visualisation of gee/cek_data_gee.js."""
    s2_rgb = sources.s2_collection(cfg, region).median().visualize(bands=["B4", "B3", "B2"], min=0, max=0.2)
    palsar = sources.palsar2_db(sources.palsar2_collection(cfg, region).mosaic())
    gedi = sources.gedi_mosaic(cfg, region, "gedi_l4a")
    images = {
        "s2_rgb": s2_rgb,
        "s1_vh": sources.s1_collection(cfg, region).median().select("VH").visualize(min=-25, max=-10),
        "palsar2_hv": palsar.select("HV_dB").visualize(min=-20, max=-8),
        "dem": sources.dem(cfg, region).visualize(min=0, max=40, palette=["2C7BB6", "FFFFBF", "D7191C"]),
        # footprints are 25 m wide; focalMax enlarges them so they stay visible at quick-look scale
        "gedi_l4a": s2_rgb.blend(
            gedi.focalMax(2).visualize(min=0, max=400, palette=["FFFF00", "FF8C00", "FF0000"])),
    }
    saved = []
    for name, image in images.items():
        t0 = time.time()
        url = image.getThumbURL({"region": region, "dimensions": THUMB_DIM, "crs": cfg["crs"], "format": "png"})
        response = requests.get(url, timeout=600)
        response.raise_for_status()
        path = out_dir / f"{name}.png"
        path.write_bytes(response.content)
        saved.append(path.name)
        print(f"  saved {path.relative_to(ROOT)}  ({time.time() - t0:.0f} s)")
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fase 1 data availability check.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--region", choices=("aoi", "smoke"), default="aoi")
    parser.add_argument("--no-thumbs", action="store_true", help="skip the quick-look PNGs")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if is_todo(cfg["gee_project"]):
        print("gee_project in the config is still TODO.", file=sys.stderr)
        return 1
    ee.Initialize(project=cfg["gee_project"])

    bbox = cfg["aoi_bbox"] if args.region == "aoi" else cfg["smoke_bbox"]
    region = sources.bbox_region(bbox)
    out_dir = ROOT / "outputs" / "data_check"
    if args.region != "aoi":
        out_dir = out_dir / args.region
    out_dir.mkdir(parents=True, exist_ok=True)

    start, end = sources.date_range(cfg)
    print(f"Data check: region {args.region} {bbox}, {start} to {end}")
    stats = compute_stats(cfg, region)
    stats["gedi_l4a_per_patch"] = gedi_per_patch(cfg, region)
    summary = {
        "region": args.region,
        "bbox": bbox,
        "date_range": [start, end],
        "gee_project": cfg["gee_project"],
        "earthengine_api": ee.__version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": stats,
    }
    if args.region == "aoi" and cfg["year"] == 2020:
        diff = compare_to_reference(stats, REFERENCE_2020_AOI)
        summary["reference_2020"] = REFERENCE_2020_AOI
        summary["relative_difference"] = diff
        print("Compared with gee/cek_data_gee.js (CLAUDE.md):")
        for key, ref in REFERENCE_2020_AOI.items():
            change = "n/a" if diff[key] is None else f"{diff[key]:+.2%}"
            print(f"  {key:<30} now {stats[key]}  ref {ref}  diff {change}")
    if not args.no_thumbs:
        summary["quicklooks"] = save_quicklooks(cfg, region, out_dir)

    path = out_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
