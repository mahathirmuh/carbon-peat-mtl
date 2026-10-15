"""Fase 2 check: exported feature GeoTIFF tiles must sit on the working grid with every band filled.

Checks CRS, pixel size, alignment with the working grid, band count and names, and that the tiles cover the
grid exactly; computes per-band statistics over valid pixels (value != nodata).
Writes outputs/features/band_stats_<region>.json.

Usage: python scripts/check_features.py --region smoke [--write-tags] data/raw/features_smoke_2020.tif [more tiles ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets `python scripts/check_features.py` import src/ from the repo root

from src.config import DEFAULT_CONFIG, load_config  # noqa: E402
from src.grid import Grid, working_grid  # noqa: E402


def check_grid(paths: list[Path], grid: Grid, bands: list[str]) -> list[str]:
    """Problems found when comparing the tiles with the working grid (empty list = all fine)."""
    problems = []
    covered = 0
    epsg = int(grid.crs.split(":")[1])
    for path in paths:
        with rasterio.open(path) as ds:
            t = ds.transform
            col, row = (t.c - grid.x0) / grid.scale, (grid.y0 - t.f) / grid.scale
            if ds.crs is None or ds.crs.to_epsg() != epsg:
                problems.append(f"{path.name}: CRS {ds.crs}, expected {grid.crs}")
            if (t.a, t.e) != (grid.scale, -grid.scale):
                problems.append(f"{path.name}: pixel size {(t.a, t.e)}, expected {(grid.scale, -grid.scale)}")
            if col != int(col) or row != int(row) or col < 0 or row < 0 \
                    or col + ds.width > grid.width or row + ds.height > grid.height:
                problems.append(f"{path.name}: origin ({t.c}, {t.f}) is not inside the working grid")
            if ds.count != len(bands):
                problems.append(f"{path.name}: {ds.count} bands, expected {len(bands)}")
            elif any(ds.descriptions) and list(ds.descriptions) != bands:
                problems.append(f"{path.name}: band names {list(ds.descriptions)} differ from the config")
            covered += ds.width * ds.height
    if covered != grid.width * grid.height:
        problems.append(f"tiles cover {covered} px, the grid has {grid.width * grid.height}")
    return problems


def write_tags(path: Path, bands: list[str], nodata: float) -> None:
    """Write the nodata value and the band names into a local GeoTIFF, so GIS tools read it correctly.

    The band order is guaranteed by gee/build_features.py, which checks it against the config before export.
    """
    with rasterio.open(path, "r+") as ds:
        ds.nodata = nodata
        for i, band in enumerate(bands, start=1):
            ds.set_band_description(i, band)


def band_stats(paths: list[Path], bands: list[str], nodata: float) -> dict:
    """Valid fraction, min, max, mean and std of every band over all tiles, excluding nodata pixels."""
    acc = {b: {"n": 0, "valid": 0, "sum": 0.0, "sumsq": 0.0, "min": np.inf, "max": -np.inf} for b in bands}
    for path in paths:
        with rasterio.open(path) as ds:
            for i, band in enumerate(bands, start=1):
                data = ds.read(i).astype(np.float64)
                valid = data[(data != nodata) & np.isfinite(data)]
                a = acc[band]
                a["n"] += data.size
                a["valid"] += valid.size
                if valid.size:
                    a["sum"] += valid.sum()
                    a["sumsq"] += np.square(valid).sum()
                    a["min"] = min(a["min"], valid.min())
                    a["max"] = max(a["max"], valid.max())
    stats = {}
    for band, a in acc.items():
        if not a["valid"]:
            stats[band] = {"valid_fraction": 0.0}
            continue
        mean = a["sum"] / a["valid"]
        stats[band] = {
            "valid_fraction": round(a["valid"] / a["n"], 6),
            "min": float(a["min"]),
            "max": float(a["max"]),
            "mean": float(mean),
            "std": float(np.sqrt(max(a["sumsq"] / a["valid"] - mean**2, 0.0))),
        }
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check exported feature GeoTIFF tiles.")
    parser.add_argument("paths", nargs="+", type=Path, help="all GeoTIFF tiles of one export")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--region", choices=("smoke", "aoi"), required=True)
    parser.add_argument("--write-tags", action="store_true",
                        help="write nodata and band names into the files (use on local copies only)")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    bands, nodata = cfg["bands"], cfg["nodata"]["float32"]
    grid = working_grid(cfg, cfg["aoi_bbox"] if args.region == "aoi" else cfg["smoke_bbox"])

    problems = check_grid(args.paths, grid, bands)
    if args.write_tags and not problems:
        for path in args.paths:
            write_tags(path, bands, nodata)
    stats = band_stats(args.paths, bands, nodata)
    problems += [f"band {b} has no valid pixels" for b, s in stats.items() if s["valid_fraction"] == 0]

    for band, s in stats.items():
        if s["valid_fraction"]:
            print(f"  {band:<18} valid {s['valid_fraction']:.4f}  min {s['min']:10.4f}  max {s['max']:10.4f}  "
                  f"mean {s['mean']:10.4f}  std {s['std']:9.4f}")
    for problem in problems:
        print(f"  PROBLEM: {problem}")

    out = ROOT / "outputs" / "features" / f"band_stats_{args.region}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "region": args.region,
        "files": [p.name for p in args.paths],
        "grid": asdict(grid),
        "nodata": nodata,
        "problems": problems,
        "bands": stats,
    }, indent=2), encoding="utf-8")
    print(f"{'OK' if not problems else 'FAILED'}: saved {out.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
