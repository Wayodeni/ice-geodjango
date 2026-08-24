from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
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


def preview_shape(width: int, height: int, max_size: int = 1800) -> tuple[int, int]:
    scale = min(1.0, max_size / max(width, height))
    return max(1, round(height * scale)), max(1, round(width * scale))


def raster_bounds_4326(src) -> list[list[float]]:
    left, bottom, right, top = src.bounds

    if src.crs and src.crs.to_epsg() != 4326:
        transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        left_lon, bottom_lat = transformer.transform(left, bottom)
        right_lon, top_lat = transformer.transform(right, top)
    else:
        left_lon, bottom_lat = left, bottom
        right_lon, top_lat = right, top

    return [[bottom_lat, left_lon], [top_lat, right_lon]]


def create_rgb_preview_png(cog_path: Path, output_png_path: Path) -> tuple[list[list[float]], Path]:
    with rasterio.open(cog_path) as src:
        # GeoTIFF bands are 1-based. For exported Sentinel-2 stack:
        # 1 = B02, 2 = B03, 3 = B04, therefore RGB = 3, 2, 1.
        height, width = preview_shape(src.width, src.height)
        blue, green, red = src.read(
            [1, 2, 3],
            out_shape=(3, height, width),
            resampling=Resampling.bilinear,
        )

        rgb = np.dstack(
            [
                normalize_band(red),
                normalize_band(green),
                normalize_band(blue),
            ]
        )

        alpha = np.all(np.isfinite(np.stack([red, green, blue])), axis=0).astype("uint8") * 255
        image = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_png_path)
        bounds = raster_bounds_4326(src)

    return bounds, output_png_path


def create_sar_preview_png(cog_path: Path, output_png_path: Path) -> tuple[list[list[float]], Path]:
    with rasterio.open(cog_path) as src:
        height, width = preview_shape(src.width, src.height)
        vv, vh = src.read(
            [1, 2],
            out_shape=(2, height, width),
            resampling=Resampling.bilinear,
        )
        vv_display = normalize_band(vv)
        vh_display = normalize_band(vh)
        difference_display = normalize_band(vv - vh)
        rgb = np.dstack([vv_display, vh_display, difference_display])
        alpha = np.all(np.isfinite(np.stack([vv, vh])), axis=0).astype("uint8") * 255

        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA").save(output_png_path)
        bounds = raster_bounds_4326(src)

    return bounds, output_png_path


def create_layer_preview(
    cog_path: Path,
    output_name: str,
    layer_type: str,
) -> tuple[Path, tuple[float, float, float, float]]:
    output_dir = settings.MEDIA_ROOT / "processing"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_png_path = output_dir / output_name
    if layer_type == "rgb":
        image_bounds, image_path = create_rgb_preview_png(cog_path, output_png_path)
    elif layer_type == "sar":
        image_bounds, image_path = create_sar_preview_png(cog_path, output_png_path)
    else:
        raise ValueError(f"Unsupported preview layer type: {layer_type}")

    return image_path, leaflet_bounds_to_extent(image_bounds)


def create_mosaic_preview(cog_path: Path, output_name: str):
    """Backward-compatible RGB preview wrapper."""
    return create_layer_preview(cog_path, output_name, "rgb")
