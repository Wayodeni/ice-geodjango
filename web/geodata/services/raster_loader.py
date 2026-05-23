import json
from rasterio.errors import RasterioIOError
from shapely.geometry import shape
import stackstac
import rioxarray  # noqa: F401

from geodata.services.bands import normalize_band_names, available_bands
from geodata.services.sensor_registry import get_sensor_spec


def _resolve_loader_args(items, *args, **kwargs):
    """Support both project pipeline calls and quick Django shell checks.

    Supported forms:
    load_stack(items, sensor_name="sentinel-2-l2a", roi=..., target_crs=..., resolution=...)
    load_stack(items, "sentinel-2-l2a", roi, target_crs, resolution)
    load_stack(items, job, sensor)
    """
    if args and hasattr(args[0], "roi"):
        job = args[0]
        sensor = args[1] if len(args) > 1 else None
        sensor_name = getattr(sensor, "name", sensor)
        return {
            "sensor_name": sensor_name,
            "roi": job.roi.polygon,
            "target_crs": job.target_crs,
            "resolution": job.resolution,
        }

    data = {
        "sensor_name": kwargs.get("sensor_name"),
        "roi": kwargs.get("roi"),
        "target_crs": kwargs.get("target_crs"),
        "resolution": kwargs.get("resolution"),
    }

    if args:
        data["sensor_name"] = data["sensor_name"] or args[0]
    if len(args) > 1:
        data["roi"] = data["roi"] or args[1]
    if len(args) > 2:
        data["target_crs"] = data["target_crs"] or args[2]
    if len(args) > 3:
        data["resolution"] = data["resolution"] or args[3]

    missing = [key for key, value in data.items() if value is None]
    if missing:
        raise ValueError(f"Missing load_stack arguments: {missing}")

    return data


def load_stack(items, job, sensor):
    if isinstance(sensor, str):
        sensor = get_sensor_spec(sensor)
    stack = stackstac.stack(
        items,
        assets=sensor.bands,
        epsg=int(job.target_crs.replace("EPSG:", "")),
        resolution=job.resolution,
        bounds_latlon=job.roi.polygon.extent,
        chunksize=256,
        errors_as_nodata=(
            RasterioIOError(".*"),
            RuntimeError(".*Read failed.*"),
            RuntimeError(".*TIFFReadEncodedTile.*"),
            RuntimeError(".*IReadBlock failed.*"),
        ),
    )

    stack = normalize_band_names(stack, sensor.name)

    stack = stack.rio.set_spatial_dims(
        x_dim="x",
        y_dim="y",
        inplace=False,
    )
    stack = stack.rio.write_crs(job.target_crs, inplace=False)

    print(f"Loaded {sensor.name} bands: {available_bands(stack)}")

    return stack