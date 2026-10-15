"""The fixed working grid (CRS, transform, size) shared by the feature stack, the labels and the patches."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Grid:
    crs: str
    x0: float      # left edge (m)
    y0: float      # top edge (m)
    scale: float   # pixel size (m)
    width: int     # pixels
    height: int    # pixels

    @property
    def transform(self) -> list[float]:
        """Affine [xScale, xShear, xOrigin, yShear, yScale, yOrigin]: Earth Engine crsTransform and rasterio order."""
        return [self.scale, 0, self.x0, 0, -self.scale, self.y0]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(left, bottom, right, top) in grid CRS units."""
        return self.x0, self.y0 - self.height * self.scale, self.x0 + self.width * self.scale, self.y0


def working_grid(cfg: dict, bbox: list[float]) -> Grid:
    """Grid in cfg['crs'] at cfg['scale'] covering a lon/lat bbox.

    Edges sit on whole multiples of the pixel size, so grids built from different boxes (AOI, smoke window)
    share pixel boundaries, and 10 m pixels line up with the Sentinel-2 10 m grid.
    """
    from rasterio.warp import transform_bounds

    scale = cfg["scale"]
    left, bottom, right, top = transform_bounds("EPSG:4326", cfg["crs"], *bbox)
    x0 = math.floor(left / scale) * scale
    y0 = math.ceil(top / scale) * scale
    width = math.ceil((right - x0) / scale)
    height = math.ceil((y0 - bottom) / scale)
    return Grid(cfg["crs"], x0, y0, scale, width, height)
