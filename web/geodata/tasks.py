from celery import shared_task
from django.core.files import File
from django.contrib.gis.geos import Polygon

from geodata.models import MosaicJob
from geodata.services.pipeline import build_mosaic_for_job


@shared_task(bind=True)
def run_mosaic_job(self, job_id):
    job = MosaicJob.objects.select_related("roi").get(pk=job_id)
    job.mark_running()

    try:
        result = build_mosaic_for_job(job)

        with open(result.cog_path, "rb") as file:
            job.output_cog.save(result.cog_path.name, File(file), save=False)

        with open(result.map_html_path, "rb") as file:
            job.preview_html.save(result.map_html_path.name, File(file), save=False)

        if result.bounds_4326:
            job.output_bounds = Polygon.from_bbox(result.bounds_4326)

        job.output_metadata = result.metadata
        job.save()
        job.mark_done()

    except Exception as exc:
        job.mark_failed(exc)
        raise
