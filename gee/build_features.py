"""Fase 2: build the 19-band input stack on the working grid and export it to Google Drive.

Band names, order and parameters come from config/config.yaml (CLAUDE.md, "Stack input"); sources and
filters come from gee/sources.py. Coarser inputs (Sentinel-2 20 m bands, PALSAR-2 25 m, DEM 30 m) are
interpolated bilinearly onto the 10 m grid. Masked pixels are written as the float32 nodata value.

Usage:
  python gee/build_features.py --region smoke             # small test export (~0.1 GB)
  python gee/build_features.py --region smoke --download  # same image straight into data/raw/ (no Drive)
  python gee/build_features.py --region aoi --yes         # full AOI (~7 GB), only after confirmation
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets `python gee/build_features.py` import gee/ and src/ from the repo root

from gee import sources  # noqa: E402
from src.config import DEFAULT_CONFIG, is_todo, load_config  # noqa: E402
from src.grid import Grid, working_grid  # noqa: E402

RESAMPLE = "bilinear"
BAND_UNITS = {
    "B2": "reflectance", "B3": "reflectance", "B4": "reflectance", "B8": "reflectance",
    "B11": "reflectance", "B12": "reflectance",
    "NDVI": "index", "EVI": "index",
    "B8_contrast": "GLCM", "B8_ent": "GLCM", "B8_var": "GLCM",
    "VV": "dB", "VH": "dB", "VH_minus_VV": "dB",
    "HH_dB": "dB (gamma0)", "HV_dB": "dB (gamma0)",
    "elevation": "m", "elevation_lowpass": "m", "slope": "degrees",
}
DONE_STATES = ("COMPLETED", "FAILED", "CANCELLED")


def elevation_lowpass(cfg: dict, dem: ee.Image) -> ee.Image:
    """Gaussian low-pass of the DSM for the dome shape.

    The DSM is mean-aggregated to a coarse grid, smoothed there and interpolated back to 10 m. With
    sigma = 500 m this equals smoothing at 10 m in practice, at about 1% of the cost.
    """
    params = cfg["dem_lowpass"]
    coarse = ee.Projection(cfg["crs"]).atScale(params["scale_m"])
    kernel = ee.Kernel.gaussian(radius=params["radius_m"], sigma=params["sigma_m"], units="meters")
    return (
        dem.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(coarse)
        .convolve(kernel).reproject(coarse)
        .resample(RESAMPLE)
        .rename("elevation_lowpass")
    )


def feature_stack(cfg: dict, region: ee.Geometry) -> ee.Image:
    """The 19 input bands in config order, as float32."""
    s2 = sources.s2_collection(cfg, region, RESAMPLE).median()
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
    evi = s2.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {"NIR": s2.select("B8"), "RED": s2.select("B4"), "BLUE": s2.select("B2")},
    ).rename("EVI")
    glcm = (
        s2.select("B8").multiply(255).toUint8()
        .glcmTexture(size=cfg["glcm_size"])
        .select(["B8_contrast", "B8_ent", "B8_var"])
    )
    s1 = sources.s1_collection(cfg, region, RESAMPLE).median()
    s1_ratio = s1.select("VH").subtract(s1.select("VV")).rename("VH_minus_VV")
    palsar = sources.palsar2_db(sources.palsar2_collection(cfg, region, RESAMPLE).mosaic())
    dem = sources.dem(cfg, region, RESAMPLE)
    slope = ee.Terrain.slope(dem).rename("slope")
    stack = ee.Image.cat([s2, ndvi, evi, glcm, s1, s1_ratio, palsar, dem, elevation_lowpass(cfg, dem), slope])
    return stack.select(cfg["bands"]).toFloat()


def export_image(cfg: dict, stack: ee.Image) -> ee.Image:
    """The image as written to file: masked pixels become the float32 nodata value."""
    # cast again after unmask: a double constant would promote the image to float64
    return stack.unmask(cfg["nodata"]["float32"]).toFloat()


def start_export(cfg: dict, image: ee.Image, grid: Grid, name: str) -> ee.batch.Task:
    """Drive export of `image` on exactly `grid` (crs + crsTransform + dimensions)."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=name,
        folder=cfg["drive_folder"],
        fileNamePrefix=name,
        crs=grid.crs,
        crsTransform=grid.transform,
        dimensions=f"{grid.width}x{grid.height}",
        maxPixels=1e13,
        fileDimensions=cfg["export_tile_px"],
        fileFormat="GeoTIFF",
        formatOptions={"noData": cfg["nodata"]["float32"]},
    )
    task.start()
    return task


def download_tiles(image: ee.Image, grid: Grid, out_dir: Path, tile_px: int = 512) -> list[Path]:
    """Fetch `image` on `grid` straight from Earth Engine as GeoTIFF tiles, without going through Drive.

    Meant for the smoke window: each request (512 x 512 px x 19 bands float32, about 20 MB) stays below the
    computePixels size limit.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for row in range(0, grid.height, tile_px):
        for col in range(0, grid.width, tile_px):
            width, height = min(tile_px, grid.width - col), min(tile_px, grid.height - row)
            transform = {"scaleX": grid.scale, "shearX": 0, "translateX": grid.x0 + col * grid.scale,
                         "shearY": 0, "scaleY": -grid.scale, "translateY": grid.y0 - row * grid.scale}
            data = ee.data.computePixels({
                "expression": image,
                "fileFormat": "GEO_TIFF",
                "grid": {"dimensions": {"width": width, "height": height},
                         "affineTransform": transform, "crsCode": grid.crs},
            })
            path = out_dir / f"tile-r{row:05d}-c{col:05d}.tif"
            path.write_bytes(data)
            paths.append(path)
            print(f"  saved {path.relative_to(ROOT)}", flush=True)
    return paths


def wait_for(task: ee.batch.Task, poll_s: int = 30) -> dict:
    """Poll the export task until it finishes, printing every state change."""
    last = None
    while True:
        status = task.status()
        if status["state"] != last:
            last = status["state"]
            print(f"  {time.strftime('%H:%M:%S')}  {last}", flush=True)
        if last in DONE_STATES:
            return status
        time.sleep(poll_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fase 2: export the 19-band feature stack to Google Drive.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--region", choices=("smoke", "aoi"), default="smoke")
    parser.add_argument("--yes", action="store_true", help="confirm the large full-AOI export")
    parser.add_argument("--no-wait", action="store_true", help="start the task and return without polling")
    parser.add_argument("--download", action="store_true",
                        help="smoke only: fetch the image straight into data/raw/ instead of exporting to Drive")
    args = parser.parse_args(argv)
    if args.download and args.region != "smoke":
        print("--download is only meant for the smoke window.", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    for key in ("gee_project", "drive_folder"):
        if is_todo(cfg[key]):
            print(f"{key} in the config is still TODO.", file=sys.stderr)
            return 1
    bbox = cfg["aoi_bbox"] if args.region == "aoi" else cfg["smoke_bbox"]
    grid = working_grid(cfg, bbox)
    size_gb = grid.width * grid.height * len(cfg["bands"]) * 4 / 1e9
    print(f"Feature stack, region {args.region}: {grid.width} x {grid.height} px, "
          f"{len(cfg['bands'])} bands float32, about {size_gb:.2f} GB", flush=True)
    if args.region == "aoi" and not args.yes:
        print("The full-AOI export is large: rerun with --yes once it is confirmed.", file=sys.stderr)
        return 1

    ee.Initialize(project=cfg["gee_project"])
    stack = feature_stack(cfg, sources.bbox_region(bbox))
    names = stack.bandNames().getInfo()
    if names != cfg["bands"]:
        print(f"Band order differs from the config: {names}", file=sys.stderr)
        return 1

    name = f"features_{args.region}_{cfg['year']}"
    out_dir = ROOT / "outputs" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)
    band_list = {
        "bands": cfg["bands"],
        "units": {band: BAND_UNITS[band] for band in cfg["bands"]},
        "dtype": "float32",
        "nodata": cfg["nodata"]["float32"],
        "crs": cfg["crs"],
        "scale_m": cfg["scale"],
    }
    (out_dir / "band_list.json").write_text(json.dumps(band_list, indent=2), encoding="utf-8")

    image = export_image(cfg, stack)
    if args.download:
        paths = download_tiles(image, grid, ROOT / "data" / "raw" / f"{name}_direct")
        print(f"  {len(paths)} tiles downloaded")
        return 0

    task = start_export(cfg, image, grid, name)
    print(f"  task {task.id}: Drive folder '{cfg['drive_folder']}', files {name}*.tif", flush=True)
    export_info = {"task_id": task.id, "name": name, "folder": cfg["drive_folder"],
                   "grid": asdict(grid), "size_gb": round(size_gb, 2)}
    info_path = out_dir / f"{name}.json"
    info_path.write_text(json.dumps(export_info, indent=2), encoding="utf-8")
    if args.no_wait:
        return 0

    status = wait_for(task)
    export_info["final_state"] = status["state"]
    info_path.write_text(json.dumps(export_info, indent=2), encoding="utf-8")
    if status["state"] != "COMPLETED":
        print(status.get("error_message", "export did not complete"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
