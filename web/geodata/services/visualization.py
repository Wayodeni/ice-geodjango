from pathlib import Path

import numpy as np
import rasterio
from django.conf import settings
from PIL import Image
from pyproj import Transformer


def leaflet_bounds_to_extent(bounds: list[list[float]]) -> tuple[float, float, float, float]:
    south, west = bounds[0]
    north, east = bounds[1]
    return west, south, east, north


def normalize_band(array: np.ndarray) -> np.ndarray:
    array = array.astype("float32")
    valid = np.isfinite(array)

    if not valid.any():
        return np.zeros(array.shape, dtype="uint8")

    p2, p98 = np.nanpercentile(array[valid], [2, 98])

    if p98 <= p2:
        return np.zeros(array.shape, dtype="uint8")

    array = np.clip((array - p2) / (p98 - p2), 0, 1)
    return (array * 255).astype("uint8")


def create_rgb_preview_png(cog_path: Path, output_png_path: Path) -> tuple[list[list[float]], Path]:
    with rasterio.open(cog_path) as src:
        # GeoTIFF bands are 1-based. For exported Sentinel-2 stack:
        # 1 = B02, 2 = B03, 3 = B04, therefore RGB = 3, 2, 1.
        red = src.read(3)
        green = src.read(2)
        blue = src.read(1)

        rgb = np.dstack(
            [
                normalize_band(red),
                normalize_band(green),
                normalize_band(blue),
            ]
        )

        image = Image.fromarray(rgb, mode="RGB")
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_png_path)

        left, bottom, right, top = src.bounds

        if src.crs and src.crs.to_epsg() != 4326:
            transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
            left_lon, bottom_lat = transformer.transform(left, bottom)
            right_lon, top_lat = transformer.transform(right, top)
        else:
            left_lon, bottom_lat = left, bottom
            right_lon, top_lat = right, top

        bounds = [
            [bottom_lat, left_lon],
            [top_lat, right_lon],
        ]

    return bounds, output_png_path


def create_mosaic_preview(cog_path: Path, output_name: str) -> tuple[Path, tuple[float, float, float, float]]:
    output_dir = settings.MEDIA_ROOT / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_png_path = output_dir / output_name

    image_bounds, image_path = create_rgb_preview_png(cog_path, output_png_path)

    return image_path, leaflet_bounds_to_extent(image_bounds)
