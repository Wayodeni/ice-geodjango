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
    rgb_cog_url = serializers.SerializerMethodField()
    sar_cog_url = serializers.SerializerMethodField()
    rgb_preview_url = serializers.SerializerMethodField()
    sar_preview_url = serializers.SerializerMethodField()
    sar_scene_date = serializers.SerializerMethodField()

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
            "rgb_cog",
            "rgb_cog_url",
            "sar_cog",
            "sar_cog_url",
            "rgb_preview",
            "rgb_preview_url",
            "sar_preview",
            "sar_preview_url",
            "rgb_bounds",
            "sar_bounds",
            "sar_scene_date",
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
            "rgb_cog",
            "sar_cog",
            "rgb_preview",
            "sar_preview",
            "rgb_bounds",
            "sar_bounds",
            "output_metadata",
            "created_at",
            "started_at",
            "finished_at",
        ]

    def get_output_cog_url(self, obj):
        return self.get_file_url(obj.output_cog)

    def get_file_url(self, field):
        request = self.context.get("request")
        if field and request:
            return request.build_absolute_uri(field.url)
        if field:
            return field.url
        return None

    def get_rgb_cog_url(self, obj):
        return self.get_file_url(obj.rgb_cog)

    def get_sar_cog_url(self, obj):
        return self.get_file_url(obj.sar_cog)

    def get_rgb_preview_url(self, obj):
        return self.get_file_url(obj.rgb_preview)

    def get_sar_preview_url(self, obj):
        return self.get_file_url(obj.sar_preview)

    def get_sar_scene_date(self, obj):
        acquired_at = obj.output_metadata.get("sar_scene_acquired_at")
        if acquired_at:
            return acquired_at[:10]

        scene_id = obj.output_metadata.get("sar_scene_id")
        scene = (
            SatelliteScene.objects
            .filter(stac_id=scene_id)
            .only("acquired_at")
            .first()
            if scene_id
            else None
        )
        return scene.acquired_at.date().isoformat() if scene else None

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
