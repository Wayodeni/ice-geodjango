from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.core.exceptions import ValidationError as DjangoValidationError

from geodata.models import MosaicJob, RegionOfInterest, SatelliteScene
from geodata.services.job_validation import normalize_and_validate_job_settings


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

    def validate(self, attrs):
        instance = self.instance
        default_sensors = ["sentinel-2-l2a"]
        default_crs = "EPSG:32643"
        default_resolution = 10
        try:
            normalized = normalize_and_validate_job_settings(
                attrs.get(
                    "selected_sensors",
                    getattr(instance, "selected_sensors", default_sensors),
                ),
                attrs.get("target_crs", getattr(instance, "target_crs", default_crs)),
                attrs.get(
                    "resolution",
                    getattr(instance, "resolution", default_resolution),
                ),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        attrs.update(normalized)
        return attrs
