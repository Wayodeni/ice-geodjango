from celery import shared_task
from django.core.files import File
from django.contrib.gis.geos import Polygon

from geodata.models import MosaicJob
from geodata.services.pipeline import build_mosaic_for_job


def save_layer_result(job, layer_name, result):
    cog_field = getattr(job, f"{layer_name}_cog")
    preview_field = getattr(job, f"{layer_name}_preview")

    with open(result.cog_path, "rb") as file:
        cog_field.save(result.cog_path.name, File(file), save=False)
    with open(result.preview_png_path, "rb") as file:
        preview_field.save(result.preview_png_path.name, File(file), save=False)

    setattr(job, f"{layer_name}_bounds", Polygon.from_bbox(result.bounds_4326))

    result.cog_path.unlink(missing_ok=True)
    result.preview_png_path.unlink(missing_ok=True)


@shared_task(bind=True)
def run_mosaic_job(self, job_id):
    job = MosaicJob.objects.select_related("roi").get(pk=job_id)
    job.mark_running()

    try:
        result = build_mosaic_for_job(job)

        if result.rgb:
            save_layer_result(job, "rgb", result.rgb)
        else:
            job.rgb_cog = None
            job.rgb_preview = None
            job.rgb_bounds = None

        if result.sar:
            save_layer_result(job, "sar", result.sar)
        else:
            job.sar_cog = None
            job.sar_preview = None
            job.sar_bounds = None

        job.output_metadata = result.metadata
        job.save()
        job.mark_done()

    except Exception as exc:
        job.mark_failed(exc)
        raise
