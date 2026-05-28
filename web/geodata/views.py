from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from geodata.models import MosaicJob, RegionOfInterest, SatelliteScene
from geodata.serializers import (
    MosaicJobSerializer,
    RegionOfInterestSerializer,
    SatelliteSceneSerializer,
)
from geodata.tasks import run_mosaic_job


class RegionOfInterestViewSet(viewsets.ModelViewSet):
    queryset = RegionOfInterest.objects.all()
    serializer_class = RegionOfInterestSerializer
    search_fields = ["name"]
    ordering_fields = ["created_at", "name"]


class SatelliteSceneViewSet(viewsets.ModelViewSet):
    queryset = SatelliteScene.objects.all()
    serializer_class = SatelliteSceneSerializer
    filterset_fields = ["sensor", "collection"]
    search_fields = ["stac_id", "collection"]
    ordering_fields = ["acquired_at", "cloud_cover", "created_at"]


class MosaicJobViewSet(viewsets.ModelViewSet):
    queryset = MosaicJob.objects.select_related("roi").all()
    serializer_class = MosaicJobSerializer
    filterset_fields = ["status", "target_date"]
    ordering_fields = ["created_at", "target_date", "finished_at"]

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        job = self.get_object()

        if job.status == MosaicJob.STATUS_RUNNING:
            return Response({"detail": "Job is already running"}, status=status.HTTP_409_CONFLICT)

        run_mosaic_job.delay(job.pk)
        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
