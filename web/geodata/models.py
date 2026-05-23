from django.contrib.gis.db import models
from django.utils import timezone


class RegionOfInterest(models.Model):
    name = models.CharField(max_length=255, blank=True)
    polygon = models.PolygonField(srid=4326)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"ROI {self.pk}"


class SatelliteScene(models.Model):
    SENSOR_SENTINEL_2 = "sentinel-2-l2a"
    SENSOR_SENTINEL_1 = "sentinel-1-rtc"

    SENSOR_CHOICES = [
        (SENSOR_SENTINEL_2, "Sentinel-2 L2A"),
        (SENSOR_SENTINEL_1, "Sentinel-1 RTC"),
    ]

    stac_id = models.CharField(max_length=512, unique=True)
    collection = models.CharField(max_length=128)
    sensor = models.CharField(max_length=64, choices=SENSOR_CHOICES)
    acquired_at = models.DateTimeField()
    cloud_cover = models.FloatField(null=True, blank=True)
    footprint = models.PolygonField(srid=4326)
    assets = models.JSONField(default=dict, blank=True)
    properties = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-acquired_at"]
        indexes = [
            models.Index(fields=["sensor", "acquired_at"]),
            models.Index(fields=["collection"]),
        ]

    def __str__(self):
        return self.stac_id


class MosaicJob(models.Model):
    STATUS_CREATED = "created"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_RUNNING, "Running"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    roi = models.ForeignKey(
        RegionOfInterest,
        on_delete=models.CASCADE,
        related_name="mosaic_jobs",
    )
    target_date = models.DateField()
    time_window_days = models.PositiveIntegerField(default=7)
    selected_sensors = models.JSONField(default=list)
    target_crs = models.CharField(max_length=32, default="EPSG:32643")
    resolution = models.FloatField(default=10.0)
    max_cloud_cover = models.FloatField(default=40.0)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_CREATED)
    error_message = models.TextField(blank=True)
    output_cog = models.FileField(upload_to="mosaics/", blank=True, null=True)
    preview_html = models.FileField(upload_to="previews/", blank=True, null=True)
    output_bounds = models.PolygonField(srid=4326, null=True, blank=True)
    output_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Mosaic job {self.pk}"

    def mark_running(self):
        self.status = self.STATUS_RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_done(self):
        self.status = self.STATUS_DONE
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])

    def mark_failed(self, message):
        self.status = self.STATUS_FAILED
        self.error_message = str(message)
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "error_message", "finished_at"])
