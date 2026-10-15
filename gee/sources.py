"""Earth Engine data sources shared by the gee/ pipeline scripts.

Filters and conversions follow CLAUDE.md (table "Google Earth Engine") and gee/cek_data_gee.js, so the data
check, the feature stack and the labels all use exactly the same images.
"""
from __future__ import annotations

import ee

S2_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]

# GEDI product -> (label band, quality flag that must equal 1); degrade_flag must equal 0 for both.
GEDI_SPECS = {
    "gedi_l4a": ("agbd", "l4_quality_flag"),
    "gedi_l2a": ("rh98", "quality_flag"),
}


def bbox_region(bbox: list[float]) -> ee.Geometry:
    """[lon_min, lat_min, lon_max, lat_max] as an Earth Engine rectangle."""
    return ee.Geometry.Rectangle(bbox)


def date_range(cfg: dict) -> tuple[str, str]:
    """Start (inclusive) and end (exclusive) of the analysis year."""
    year = cfg["year"]
    return f"{year}-01-01", f"{year + 1}-01-01"


def s2_collection(cfg: dict, region: ee.Geometry) -> ee.ImageCollection:
    """Sentinel-2 SR masked with Cloud Score+ (cs_cdf >= threshold); S2_BANDS as reflectance 0-1."""
    start, end = date_range(cfg)
    threshold = cfg["cs_cdf_threshold"]
    cs_plus = ee.ImageCollection(cfg["datasets"]["cloud_score_plus"])
    return (
        ee.ImageCollection(cfg["datasets"]["s2_sr"])
        .filterBounds(region)
        .filterDate(start, end)
        .linkCollection(cs_plus, ["cs_cdf"])
        .map(lambda img: img.updateMask(img.select("cs_cdf").gte(threshold)).select(S2_BANDS).divide(10000))
    )


def s1_collection(cfg: dict, region: ee.Geometry) -> ee.ImageCollection:
    """Sentinel-1 GRD scenes in IW mode with both VV and VH (values already in dB)."""
    start, end = date_range(cfg)
    return (
        ee.ImageCollection(cfg["datasets"]["s1_grd"])
        .filterBounds(region)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV", "VH"])
    )


def palsar2_collection(cfg: dict, region: ee.Geometry) -> ee.ImageCollection:
    """ALOS PALSAR-2 yearly mosaic images (DN) of the analysis year."""
    start, end = date_range(cfg)
    return ee.ImageCollection(cfg["datasets"]["palsar2_yearly"]).filterBounds(region).filterDate(start, end)


def palsar2_db(image: ee.Image) -> ee.Image:
    """HH and HV from DN to gamma0 in dB: 10*log10(DN^2) - 83.0, masked where DN == 0."""
    bands = []
    for band in ("HH", "HV"):
        dn = image.select(band).toFloat()
        bands.append(dn.pow(2).log10().multiply(10).subtract(83.0).updateMask(dn.gt(0)).rename(f"{band}_dB"))
    return ee.Image.cat(bands)


def dem(cfg: dict, region: ee.Geometry) -> ee.Image:
    """Copernicus DEM (a DSM) mosaic with the tile projection restored, as ee.Terrain needs."""
    col = ee.ImageCollection(cfg["datasets"]["dem"])
    return (
        col.filterBounds(region).select("DEM").mosaic()
        .setDefaultProjection(col.first().projection())
        .rename("elevation")
    )


def gedi_mosaic(cfg: dict, region: ee.Geometry, product: str) -> ee.Image:
    """Quality-filtered GEDI monthly rasters of the year, mosaicked into one band (25 m footprints)."""
    band, flag = GEDI_SPECS[product]
    start, end = date_range(cfg)
    return (
        ee.ImageCollection(cfg["datasets"][product])
        .filterBounds(region)
        .filterDate(start, end)
        .map(lambda im: im.updateMask(im.select(flag).eq(1)).updateMask(im.select("degrade_flag").eq(0)))
        .select(band)
        .mosaic()
    )


def peatgrids(cfg: dict) -> tuple[ee.Image, ee.Image]:
    """PEATGRIDS mean thickness (cm) and carbon stock (Mg C/m2), with negative values masked."""
    thick = ee.Image(cfg["datasets"]["peatgrids_thickness"]).select("THICKNESS_CM_MEAN")
    c_stock = ee.Image(cfg["datasets"]["peatgrids_c_stock"]).select("C_STOCK_MgC_per_m2_MEAN")
    return thick.updateMask(thick.gte(0)), c_stock.updateMask(c_stock.gte(0))
