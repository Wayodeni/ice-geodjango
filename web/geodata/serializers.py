from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from geodata.models import MosaicJob, RegionOfInterest, SatelliteScene


class RegionOfInterestSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = RegionOfInterest
        geo_field = "polygon"
        fields = ["id", "name", "polygon", "properties", "created_at"]
        read_only_fields = ["id", "created_at"]


class SatelliteSceneSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = SatelliteScene
        geo_field = "footprint"
        fields = [
            "id",
            "stac_id",
            "collection",
            "sensor",
            "acquired_at",
            "cloud_cover",
            "footprint",
            "assets",
            "properties",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MosaicJobSerializer(serializers.ModelSerializer):
    output_cog_url = serializers.SerializerMethodField()

    class Meta:
        model = MosaicJob
        fields = [
            "id",
            "roi",
            "target_date",
            "time_window_days",
            "selected_sensors",
            "target_crs",
            "resolution",
            "max_cloud_cover",
            "status",
            "error_message",
            "output_cog",
            "output_cog_url",
            "output_metadata",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "error_message",
            "output_cog",
            "output_metadata",
            "created_at",
            "started_at",
            "finished_at",
        ]

    def get_output_cog_url(self, obj):
        request = self.context.get("request")
        if obj.output_cog and request:
            return request.build_absolute_uri(obj.output_cog.url)
        if obj.output_cog:
            return obj.output_cog.url
        return None
