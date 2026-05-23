from rest_framework.routers import DefaultRouter

from geodata.views import MosaicJobViewSet, RegionOfInterestViewSet, SatelliteSceneViewSet

router = DefaultRouter()
router.register("rois", RegionOfInterestViewSet, basename="roi")
router.register("scenes", SatelliteSceneViewSet, basename="scene")
router.register("mosaic-jobs", MosaicJobViewSet, basename="mosaic-job")

urlpatterns = router.urls
