from datetime import date

from django.contrib.gis.geos import Polygon
from django.core.management.base import BaseCommand

from geodata.models import MosaicJob, RegionOfInterest


class Command(BaseCommand):
    help = "Create a demo ROI and mosaic job"

    def handle(self, *args, **options):
        roi = RegionOfInterest.objects.create(
            name="Demo mountain ice ROI",
            polygon=Polygon(
                (
                    (76.80, 43.05),
                    (77.10, 43.05),
                    (77.10, 43.30),
                    (76.80, 43.30),
                    (76.80, 43.05),
                ),
                srid=4326,
            ),
        )
        job = MosaicJob.objects.create(
            roi=roi,
            target_date=date(2024, 8, 1),
            time_window_days=7,
            selected_sensors=["sentinel-2-l2a"],
            target_crs="EPSG:32643",
            resolution=10,
            max_cloud_cover=40,
        )
        self.stdout.write(self.style.SUCCESS(f"Created ROI {roi.pk} and job {job.pk}"))
