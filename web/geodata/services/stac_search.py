from datetime import datetime, time, timedelta, timezone

import json
import planetary_computer
from django.contrib.gis.geos import GEOSGeometry, Polygon
from pystac_client import Client

from geodata.models import SatelliteScene
from geodata.services.dates import coerce_date
from geodata.services.sensor_registry import get_sensor_spec

STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def get_datetime_range(job) -> str:
    target_date = coerce_date(job.target_date)
    start_date = target_date - timedelta(days=job.time_window_days)
    end_date = target_date + timedelta(days=job.time_window_days)
    return f"{start_date.isoformat()}/{end_date.isoformat()}"


def search_stac_items(job, sensor_name: str):
    sensor = get_sensor_spec(sensor_name)
    catalog = Client.open(STAC_API_URL)

    query = {}
    if sensor.is_optical and sensor.cloud_property:
        query[sensor.cloud_property] = {"lt": job.max_cloud_cover}

    search = catalog.search(
        collections=[sensor.collection],
        intersects=json.loads(job.roi.polygon.geojson),
        datetime=get_datetime_range(job),
        query=query,
    )

    return [planetary_computer.sign(item) for item in search.items()]


def save_items_to_database(items, sensor_name: str):
    sensor = get_sensor_spec(sensor_name)
    saved_scenes = []

    for item in items:
        geom = GEOSGeometry(json.dumps(item.geometry), srid=4326)
        if geom.geom_type == "MultiPolygon":
            geom = geom.convex_hull
        if not isinstance(geom, Polygon):
            geom = geom.envelope

        acquired_at = item.datetime
        if acquired_at is None:
            value = item.properties.get("datetime")
            acquired_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if acquired_at.tzinfo is None:
            acquired_at = acquired_at.replace(tzinfo=timezone.utc)

        cloud_cover = item.properties.get(sensor.cloud_property) if sensor.cloud_property else None
        assets = {key: asset.href for key, asset in item.assets.items()}

        scene, _ = SatelliteScene.objects.update_or_create(
            stac_id=item.id,
            defaults={
                "collection": sensor.collection,
                "sensor": sensor_name,
                "acquired_at": acquired_at,
                "cloud_cover": cloud_cover,
                "footprint": geom,
                "assets": assets,
                "properties": dict(item.properties),
            },
        )
        saved_scenes.append(scene)

    return saved_scenes


def find_candidate_scenes(job):
    target_date = coerce_date(job.target_date)
    start_datetime = datetime.combine(target_date - timedelta(days=job.time_window_days), time.min, tzinfo=timezone.utc)
    end_datetime = datetime.combine(target_date + timedelta(days=job.time_window_days), time.max, tzinfo=timezone.utc)

    queryset = SatelliteScene.objects.filter(
        sensor__in=job.selected_sensors,
        acquired_at__gte=start_datetime,
        acquired_at__lte=end_datetime,
        footprint__intersects=job.roi.polygon,
    )

    if "sentinel-2-l2a" in job.selected_sensors:
        queryset = queryset.exclude(
            sensor="sentinel-2-l2a",
            cloud_cover__gt=job.max_cloud_cover,
        )

    return queryset



def search_items(job, sensor_or_name):
    """Compatibility wrapper for quick debugging from Django shell.

    Accepts either a sensor name string or a SensorSpec-like object.
    """
    sensor_name = getattr(sensor_or_name, "name", sensor_or_name)
    return search_stac_items(job, sensor_name)
