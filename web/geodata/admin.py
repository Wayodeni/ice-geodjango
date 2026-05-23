from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from geodata.models import MosaicJob, RegionOfInterest, SatelliteScene


@admin.register(RegionOfInterest)
class RegionOfInterestAdmin(GISModelAdmin):
    list_display = ["id", "name", "created_at"]
    search_fields = ["name"]


@admin.register(SatelliteScene)
class SatelliteSceneAdmin(GISModelAdmin):
    list_display = ["id", "stac_id", "sensor", "collection", "acquired_at", "cloud_cover"]
    list_filter = ["sensor", "collection"]
    search_fields = ["stac_id", "collection"]


@admin.register(MosaicJob)
class MosaicJobAdmin(GISModelAdmin):
    list_display = ["id", "roi", "target_date", "status", "created_at", "finished_at"]
    list_filter = ["status", "target_date"]
    search_fields = ["roi__name"]
    readonly_fields = ["started_at", "finished_at", "error_message"]
