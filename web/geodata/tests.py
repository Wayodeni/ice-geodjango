from django.contrib.gis.geos import Polygon
from django.test import TestCase

from geodata.models import MosaicJob, RegionOfInterest
from geodata.services.stac_search import get_datetime_range
from geodata.views_ui import job_to_dict


class RegionOfInterestModelTest(TestCase):
    def test_create_roi_and_job(self):
        roi = RegionOfInterest.objects.create(
            name="Test ROI",
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
            target_date="2024-08-01",
            selected_sensors=["sentinel-2-l2a"],
        )

        self.assertEqual(str(roi), "Test ROI")
        self.assertEqual(job.status, MosaicJob.STATUS_CREATED)
        self.assertEqual(get_datetime_range(job), "2024-07-25/2024-08-08")
        self.assertEqual(job_to_dict(job)["target_date"], "2024-08-01")
