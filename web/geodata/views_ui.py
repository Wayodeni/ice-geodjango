import json

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from geodata.models import MosaicJob, RegionOfInterest
from geodata.services.dates import coerce_date
from geodata.tasks import run_mosaic_job


def roi_manager_page(request):
    return render(request, "geodata/roi_manager.html")


def roi_to_feature(roi: RegionOfInterest) -> dict:
    return {
        "type": "Feature",
        "id": roi.pk,
        "properties": {
            "id": roi.pk,
            "name": roi.name,
            "created_at": roi.created_at.isoformat() if roi.created_at else None,
        },
        "geometry": json.loads(roi.polygon.geojson),
    }


def bounds_to_leaflet(bounds) -> list[list[float]]:
    west, south, east, north = bounds
    return [[south, west], [north, east]]


def get_preview_image_url(job: MosaicJob):
    image_names = [f"previews/mosaic_job_{job.pk}.png"]

    for image_name in image_names:
        image_path = settings.MEDIA_ROOT / image_name
        if image_path.exists():
            return settings.MEDIA_URL + image_name.replace("\\", "/")

    return None


def job_to_dict(job: MosaicJob) -> dict:
    preview_bounds = None
    if job.output_bounds:
        preview_bounds = bounds_to_leaflet(job.output_bounds.extent)
    elif job.roi:
        preview_bounds = bounds_to_leaflet(job.roi.polygon.extent)

    return {
        "id": job.pk,
        "roi_id": job.roi_id,
        "roi_name": job.roi.name if job.roi else None,
        "target_date": coerce_date(job.target_date).isoformat(),
        "time_window_days": job.time_window_days,
        "selected_sensors": job.selected_sensors,
        "target_crs": job.target_crs,
        "resolution": job.resolution,
        "max_cloud_cover": job.max_cloud_cover,
        "status": job.status,
        "error_message": job.error_message,
        "output_cog": job.output_cog.url if job.output_cog else None,
        "preview_image": get_preview_image_url(job),
        "preview_bounds": preview_bounds,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@require_http_methods(["GET", "POST"])
def roi_collection_api(request):
    if request.method == "GET":
        rois = RegionOfInterest.objects.all().order_by("-created_at")

        return JsonResponse({
            "type": "FeatureCollection",
            "features": [roi_to_feature(roi) for roi in rois],
        })

    payload = json.loads(request.body.decode("utf-8"))

    geometry = payload.get("geometry")
    name = payload.get("name") or "ROI"

    if not geometry:
        return JsonResponse({"detail": "Geometry is required."}, status=400)

    polygon = GEOSGeometry(json.dumps(geometry), srid=4326)

    roi = RegionOfInterest.objects.create(
        name=name,
        polygon=polygon,
    )

    return JsonResponse(roi_to_feature(roi), status=201)


@require_http_methods(["PATCH", "DELETE"])
def roi_detail_api(request, roi_id: int):
    roi = get_object_or_404(RegionOfInterest, pk=roi_id)

    if request.method == "DELETE":
        roi.delete()
        return JsonResponse({"detail": "ROI deleted."})

    payload = json.loads(request.body.decode("utf-8"))

    if "name" in payload:
        roi.name = payload["name"]

    if "geometry" in payload:
        roi.polygon = GEOSGeometry(json.dumps(payload["geometry"]), srid=4326)

    roi.save()

    return JsonResponse(roi_to_feature(roi))


@require_http_methods(["GET", "POST"])
def job_collection_api(request):
    if request.method == "GET":
        jobs = (
            MosaicJob.objects
            .select_related("roi")
            .all()
            .order_by("-created_at")[:50]
        )

        return JsonResponse({
            "results": [job_to_dict(job) for job in jobs],
        })

    payload = json.loads(request.body.decode("utf-8"))

    roi_id = payload.get("roi_id")
    if not roi_id:
        return JsonResponse({"detail": "roi_id is required."}, status=400)

    roi = get_object_or_404(RegionOfInterest, pk=roi_id)

    job = MosaicJob.objects.create(
        roi=roi,
        target_date=payload["target_date"],
        time_window_days=int(payload.get("time_window_days", 7)),
        selected_sensors=payload.get("selected_sensors", ["sentinel-2-l2a"]),
        target_crs=payload.get("target_crs", "EPSG:32643"),
        resolution=float(payload.get("resolution", 10)),
        max_cloud_cover=float(payload.get("max_cloud_cover", 40)),
    )

    return JsonResponse(job_to_dict(job), status=201)


@require_http_methods(["POST"])
def run_job_api(request, job_id: int):
    job = get_object_or_404(MosaicJob, pk=job_id)

    if job.status == MosaicJob.STATUS_RUNNING:
        return JsonResponse(
            {"detail": "Job is already running.", "job": job_to_dict(job)},
            status=409,
        )

    job.status = MosaicJob.STATUS_CREATED
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    run_mosaic_job.delay(job.pk)

    return JsonResponse({
        "detail": "Job started.",
        "job": job_to_dict(job),
    }, status=202)
