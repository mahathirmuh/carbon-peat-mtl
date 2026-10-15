"""Initialise Earth Engine with gee_project from the config and check every dataset ID.

Usage: python gee/auth_check.py [--config config/config.yaml]
Exit code 0 only if initialisation works and all configured assets are readable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets `python gee/auth_check.py` import src/ from the repo root

from src.config import DEFAULT_CONFIG, is_todo, load_config  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Earth Engine access for this project.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    project = cfg["gee_project"]
    if is_todo(project):
        print("gee_project in the config is still TODO: fill in your Cloud project ID first.", file=sys.stderr)
        return 1

    import ee  # imported here so the TODO check above works without earthengine-api

    try:
        ee.Initialize(project=project)
    except Exception as exc:  # missing credentials, unregistered project, no network, ...
        print(f"Earth Engine initialisation failed: {exc}", file=sys.stderr)
        print("Run `earthengine authenticate` once, then try again.", file=sys.stderr)
        return 1

    aoi_km2 = ee.Geometry.Rectangle(cfg["aoi_bbox"]).area(maxError=1).divide(1e6).getInfo()
    print(f"earthengine-api  {ee.__version__}")
    print(f"project          {project}")
    print(f"AOI              {cfg['aoi_bbox']}  ({aoi_km2:,.0f} km2)")

    print("assets:")
    failed = 0
    for name, asset_id in {**cfg["datasets"], **cfg["assets"]}.items():
        if is_todo(asset_id):
            print(f"  {name:<20} TODO")
            continue
        try:
            asset_type = ee.data.getAsset(asset_id)["type"]
            print(f"  {name:<20} {asset_type:<17} {asset_id}")
        except ee.EEException as exc:
            failed += 1
            print(f"  {name:<20} {'ERROR':<17} {asset_id}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
