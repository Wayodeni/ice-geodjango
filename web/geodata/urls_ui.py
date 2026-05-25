from django.urls import path

from geodata import views_ui

app_name = "geodata_ui"

urlpatterns = [
    path("", views_ui.roi_manager_page, name="roi-manager"),

    path("api/rois/", views_ui.roi_collection_api, name="roi-collection-api"),
    path("api/rois/<int:roi_id>/", views_ui.roi_detail_api, name="roi-detail-api"),

    path("api/jobs/", views_ui.job_collection_api, name="job-collection-api"),
    path("api/jobs/<int:job_id>/run/", views_ui.run_job_api, name="run-job-api"),
]