import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry

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
    coverage_ratio: float | None = None


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


def item_roi_coverage(item, roi, target_crs: str) -> float:
    if not item.geometry:
        return 0.0

    roi_geometry = roi.clone()
    item_geometry = GEOSGeometry(json.dumps(item.geometry), srid=4326)
    target_srid = int(target_crs.removeprefix("EPSG:"))
    roi_geometry.transform(target_srid)
    item_geometry.transform(target_srid)

    if roi_geometry.area <= 0:
        raise ValueError("ROI has zero area; SAR coverage cannot be calculated.")

    intersection = item_geometry.intersection(roi_geometry)
    return min(1.0, max(0.0, intersection.area / roi_geometry.area))


def select_sar_item(job, items, target_date, minimum_coverage: float = 0.99):
    start_date = target_date - timedelta(days=job.time_window_days)
    end_date = target_date + timedelta(days=job.time_window_days)

    if not items:
        raise ValueError(
            "No Sentinel-1 scenes found for "
            f"{start_date.isoformat()} through {end_date.isoformat()}."
        )

    candidates = [
        (item, item_roi_coverage(item, job.roi.polygon, job.target_crs))
        for item in items
    ]
    suitable = [candidate for candidate in candidates if candidate[1] >= minimum_coverage]

    if not suitable:
        maximum_coverage = max(coverage for _, coverage in candidates)
        raise ValueError(
            "No single Sentinel-1 scene covers at least "
            f"{minimum_coverage * 100:.0f}% of ROI within "
            f"{start_date.isoformat()} through {end_date.isoformat()}. "
            f"Checked {len(candidates)} candidate(s); maximum coverage is "
            f"{maximum_coverage * 100:.1f}%. Change the target date/time window "
            "or reduce the ROI."
        )

    target_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    return min(
        suitable,
        key=lambda candidate: (
            abs(item_datetime(candidate[0]) - target_datetime),
            -candidate[1],
            candidate[0].id,
        ),
    )


def export_layer(
    data_array,
    job,
    layer_type: str,
    scene_ids: list[str],
    acquired_at: datetime | None = None,
    coverage_ratio: float | None = None,
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
        coverage_ratio=coverage_ratio,
    )


def build_rgb_layer(job, items):
    sensor = get_sensor_spec("sentinel-2-l2a")
    stack = load_stack(items=items, job=job, sensor=sensor)
    rgb_stack = stack.sel(band=["B02", "B03", "B04"])
    # No SCL/cloud mask: every source pixel remains available to the period mosaic.
    rgb_mosaic = build_optical_mosaic(rgb_stack)
    return export_layer(rgb_mosaic, job, "rgb", [item.id for item in items])


def build_sar_layer(job, item, coverage_ratio):
    sensor = get_sensor_spec("sentinel-1-rtc")
    # Classification input must remain one acquisition, not a temporal mosaic.
    stack = load_stack(items=[item], job=job, sensor=sensor)
    sar_scene = stack.sel(band=["vv", "vh"]).isel(time=0, drop=True)
    return export_layer(
        sar_scene,
        job,
        "sar",
        [item.id],
        acquired_at=item_datetime(item),
        coverage_ratio=coverage_ratio,
    )


def build_mosaic_for_job(job) -> MosaicBuildResult:
    target_date = coerce_date(job.target_date)
    rgb_result = None
    sar_result = None
    scenes_count = {}
    items_by_sensor = {}

    for sensor_name in job.selected_sensors:
        items = search_stac_items(job, sensor_name)
        save_items_to_database(items, sensor_name)
        items_by_sensor[sensor_name] = items

    selected_sar = None
    sar_candidates_count = 0
    if "sentinel-1-rtc" in job.selected_sensors:
        sar_items = items_by_sensor.get("sentinel-1-rtc", [])
        sar_candidates_count = len(sar_items)
        selected_sar = select_sar_item(job, sar_items, target_date)

    for sensor_name in job.selected_sensors:
        items = items_by_sensor[sensor_name]
        if sensor_name == "sentinel-2-l2a":
            scenes_count[sensor_name] = len(items)
            if items:
                rgb_result = build_rgb_layer(job, items)
        elif sensor_name == "sentinel-1-rtc":
            scenes_count[sensor_name] = 1
            sar_item, coverage_ratio = selected_sar
            sar_result = build_sar_layer(job, sar_item, coverage_ratio)

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
            "sar_scene_coverage_pct": (
                round(sar_result.coverage_ratio * 100, 3)
                if sar_result and sar_result.coverage_ratio is not None
                else None
            ),
            "sar_candidates_count": sar_candidates_count,
        },
    )
