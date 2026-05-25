from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("geodata.urls")),
    path("", RedirectView.as_view(pattern_name="mosaic-job-list", permanent=False)),
    path("geo/", include("geodata.urls_ui")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
