import json
from pathlib import Path

import folium
import numpy as np
import rasterio
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from PIL import Image
from pyproj import Transformer


def roi_to_feature_collection(roi):
    if isinstance(roi, GEOSGeometry):
        geometry = json.loads(roi.geojson)
    elif isinstance(roi, str):
        geometry = json.loads(roi)
    else:
        geometry = roi

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "ROI"},
                "geometry": geometry,
            }
        ],
    }


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


def create_mosaic_map(cog_path: Path, roi, output_name: str) -> Path:
    output_dir = settings.MEDIA_ROOT / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_html_path = output_dir / output_name
    output_png_path = output_dir / output_name.replace(".html", ".png")

    center = [roi.centroid.y, roi.centroid.x]

    m = folium.Map(
        location=center,
        zoom_start=9,
        tiles="OpenStreetMap",
    )

    roi_geojson = roi_to_feature_collection(roi)

    folium.GeoJson(
        roi_geojson,
        name="ROI",
        style_function=lambda feature: {
            "color": "red",
            "weight": 2,
            "fillOpacity": 0.0,
        },
    ).add_to(m)

    image_bounds, image_path = create_rgb_preview_png(cog_path, output_png_path)

    folium.raster_layers.ImageOverlay(
        image=str(image_path),
        bounds=image_bounds,
        name="Mosaic preview",
        opacity=0.75,
        interactive=True,
        cross_origin=False,
    ).add_to(m)

    folium.LayerControl().add_to(m)

    m.save(str(output_html_path))

    return output_html_path