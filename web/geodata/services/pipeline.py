from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path

from geodata.services.bands import available_bands
from geodata.services.dates import coerce_date
from geodata.services.export import save_data_array_as_cog
from geodata.services.mosaic import build_optical_mosaic
from geodata.services.raster_loader import load_stack
from geodata.services.sensor_registry import get_sensor_spec
from geodata.services.stac_search import search_stac_items, save_items_to_database
from geodata.services.visualization import create_layer_preview


@dataclass
class RasterLayerBuildResult:
    cog_path: Path
    preview_png_path: Path
    bounds_4326: tuple[float, float, float, float]
    scene_ids: list[str]
    acquired_at: datetime | None = None


@dataclass
class MosaicBuildResult:
    rgb: RasterLayerBuildResult | None
    sar: RasterLayerBuildResult | None
    metadata: dict


def item_datetime(item) -> datetime:
    value = item.datetime
    if value is None:
        raw_value = item.properties.get("datetime")
        value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def closest_item(items, target_date):
    target_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    return min(items, key=lambda item: abs(item_datetime(item) - target_datetime))


def export_layer(
    data_array,
    job,
    layer_type: str,
    scene_ids: list[str],
    acquired_at: datetime | None = None,
):
    print(f"Exporting {layer_type.upper()} layer bands: {available_bands(data_array)}")
    artifact_type = "scene" if layer_type == "sar" else "mosaic"
    cog_path = save_data_array_as_cog(
        data_array,
        f"{layer_type}_{artifact_type}_job_{job.pk}.tif",
    )
    preview_png_path, bounds_4326 = create_layer_preview(
        cog_path,
        f"{layer_type}_{artifact_type}_job_{job.pk}.png",
        layer_type,
    )
    return RasterLayerBuildResult(
        cog_path=cog_path,
        preview_png_path=preview_png_path,
        bounds_4326=bounds_4326,
        scene_ids=scene_ids,
        acquired_at=acquired_at,
    )


def build_rgb_layer(job, items):
    sensor = get_sensor_spec("sentinel-2-l2a")
    stack = load_stack(items=items, job=job, sensor=sensor)
    rgb_stack = stack.sel(band=["B02", "B03", "B04"])
    # No SCL/cloud mask: every source pixel remains available to the period mosaic.
    rgb_mosaic = build_optical_mosaic(rgb_stack)
    return export_layer(rgb_mosaic, job, "rgb", [item.id for item in items])


def build_sar_layer(job, items, target_date):
    sensor = get_sensor_spec("sentinel-1-rtc")
    item = closest_item(items, target_date)
    # Classification input must remain one acquisition, not a temporal mosaic.
    stack = load_stack(items=[item], job=job, sensor=sensor)
    sar_scene = stack.sel(band=["vv", "vh"]).isel(time=0, drop=True)
    return export_layer(
        sar_scene,
        job,
        "sar",
        [item.id],
        acquired_at=item_datetime(item),
    )


def build_mosaic_for_job(job) -> MosaicBuildResult:
    target_date = coerce_date(job.target_date)
    rgb_result = None
    sar_result = None
    scenes_count = {}

    for sensor_name in job.selected_sensors:
        items = search_stac_items(job, sensor_name)
        save_items_to_database(items, sensor_name)

        if sensor_name == "sentinel-2-l2a":
            scenes_count[sensor_name] = len(items)
            if items:
                rgb_result = build_rgb_layer(job, items)
        elif sensor_name == "sentinel-1-rtc":
            scenes_count[sensor_name] = 1 if items else 0
            if items:
                sar_result = build_sar_layer(job, items, target_date)

    if rgb_result is None and sar_result is None:
        raise ValueError("No satellite scenes found for the selected period and ROI.")

    return MosaicBuildResult(
        rgb=rgb_result,
        sar=sar_result,
        metadata={
            "job_id": job.pk,
            "roi_id": job.roi_id,
            "target_date": target_date.isoformat(),
            "time_window_days": job.time_window_days,
            "selected_sensors": job.selected_sensors,
            "target_crs": job.target_crs,
            "resolution": job.resolution,
            "max_cloud_cover": job.max_cloud_cover,
            "scenes_count": scenes_count,
            "rgb_scene_ids": rgb_result.scene_ids if rgb_result else [],
            "sar_scene_id": sar_result.scene_ids[0] if sar_result else None,
            "sar_scene_acquired_at": (
                sar_result.acquired_at.isoformat()
                if sar_result and sar_result.acquired_at
                else None
            ),
        },
    )
