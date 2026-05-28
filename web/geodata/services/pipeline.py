from dataclasses import dataclass
from pathlib import Path
import rioxarray
from geodata.services.sensor_registry import get_sensor_spec
from geodata.services.bands import available_bands
from geodata.services.dates import coerce_date
from geodata.services.features import create_feature_stack
from geodata.services.export import save_feature_stack_as_cog
from geodata.services.masks import apply_masks
from geodata.services.mosaic import build_optical_mosaic, build_sar_mosaic
from geodata.services.raster_loader import load_stack
from geodata.services.stac_search import search_stac_items, save_items_to_database
from geodata.services.visualization import create_mosaic_preview


@dataclass
class MosaicBuildResult:
    cog_path: Path
    preview_png_path: Path
    bounds_4326: tuple[float, float, float, float]
    metadata: dict


def build_mosaic_for_job(job) -> MosaicBuildResult:
    mosaics = {}
    scenes_count = {}
    target_date = coerce_date(job.target_date)

    for sensor_name in job.selected_sensors:
        sensor = get_sensor_spec(sensor_name)

        items = search_stac_items(job, sensor_name)
        items = items[:1]
        save_items_to_database(items, sensor_name)
        scenes_count[sensor_name] = len(items)

        if not items:
            continue

        stack = load_stack(
            items=items,
            job=job,
            sensor=sensor,
        )

        print(f"{sensor_name} stack bands before masks: {available_bands(stack)}")
        masked_stack = apply_masks(stack, sensor_name)
        print(f"{sensor_name} stack bands after masks: {available_bands(masked_stack)}")

        if sensor_name == "sentinel-2-l2a":
            mosaic = build_optical_mosaic(masked_stack)
        elif sensor_name == "sentinel-1-rtc":
            mosaic = build_sar_mosaic(masked_stack)
        else:
            continue

        print(f"{sensor_name} mosaic bands: {available_bands(mosaic)}")
        mosaics[sensor_name] = mosaic

    feature_stack = create_feature_stack(mosaics)

    cog_path = save_feature_stack_as_cog(feature_stack, f"mosaic_job_{job.pk}.tif")
    preview_png_path, bounds_4326 = create_mosaic_preview(
        cog_path,
        f"mosaic_job_{job.pk}.png",
    )

    return MosaicBuildResult(
        cog_path=cog_path,
        preview_png_path=preview_png_path,
        bounds_4326=bounds_4326,
        metadata={
            "job_id": job.pk,
            "roi_id": job.roi_id,
            "target_date": target_date.isoformat(),
            "time_window_days": job.time_window_days,
            "selected_sensors": job.selected_sensors,
            "target_crs": job.target_crs,
            "resolution": job.resolution,
            "max_cloud_cover": job.max_cloud_cover,
            "preview_png": str(preview_png_path.name),
            "scenes_count": scenes_count,
        },
    )
