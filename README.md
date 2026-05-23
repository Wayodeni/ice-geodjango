# Ice GeoDjango Project

GeoDjango project for collecting satellite geodata, storing ROI polygons and scene footprints in PostGIS, building mosaics and exporting Cloud Optimized GeoTIFF results.

## Main components

- Django 5.2 + GeoDjango
- PostgreSQL 17 + PostGIS 3.5
- Celery + Redis for long-running mosaic jobs
- DRF API for ROI and mosaic job management
- Leaflet/leafmap-based preview page for final COG/map outputs
- Modular service layer for STAC search, masking, mosaicking, feature stack creation and export

## Development startup

```bash
cp .env.example .env
docker compose -f compose-dev.yml up --build
```

The application will be available at:

```text
http://localhost:8000
```

Admin panel:

```text
http://localhost:8000/admin/
```

Default development superuser:

```text
username: admin
email: admin@example.com
password: admin
```

## Production-like startup

```bash
cp .env.example .env
docker compose -f compose.yml up --build -d
```

## Main API endpoints

```text
GET    /api/rois/
POST   /api/rois/
GET    /api/rois/{id}/

GET    /api/scenes/
GET    /api/mosaic-jobs/
POST   /api/mosaic-jobs/
GET    /api/mosaic-jobs/{id}/
POST   /api/mosaic-jobs/{id}/run/
GET    /api/mosaic-jobs/{id}/map/
```

## Example ROI request

```json
{
  "type": "Feature",
  "properties": {
    "name": "Test ROI"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [76.80, 43.05],
        [77.10, 43.05],
        [77.10, 43.30],
        [76.80, 43.30],
        [76.80, 43.05]
      ]
    ]
  }
}
```

## Example mosaic job request

```json
{
  "roi": 1,
  "target_date": "2024-08-01",
  "time_window_days": 7,
  "selected_sensors": ["sentinel-2-l2a"],
  "target_crs": "EPSG:32643",
  "resolution": 10,
  "max_cloud_cover": 40
}
```

## Demo data

```bash
docker compose -f compose-dev.yml exec web python manage.py create_demo_job
```

Then open `/api/mosaic-jobs/` and run a job through `/api/mosaic-jobs/{id}/run/`.

## Notes

GeoDjango/PostGIS stores geometry, metadata, jobs and result references. Heavy raster work is performed by Python geospatial libraries in Celery workers.

## Notes about the patched geodata pipeline

This version includes several stability/debugging fixes for the satellite mosaic pipeline:

- `search_items(job, sensor)` was added as a compatibility wrapper around `search_stac_items(job, sensor_name)` for quick Django shell checks.
- `load_stack(...)` now accepts both the project pipeline signature and the quick shell signature `load_stack(items, job, sensor)`.
- Sentinel-2 and Sentinel-1 band names are normalized in `geodata/services/bands.py`.
- Missing bands now raise a clear `ValueError` with the list of available bands.
- The Celery worker in `compose-dev.yml` runs with `--concurrency=1` to reduce remote COG read failures.
- GDAL HTTP retry environment variables were added to web and Celery services.
- The Docker base image was changed to Python 3.11 for better geospatial package stability.

Fast band check from Django shell:

```bash
docker compose -f compose-dev.yml exec web python manage.py shell
```

```python
from geodata.models import MosaicJob
from geodata.services.sensor_registry import get_sensor_spec
from geodata.services.stac_search import search_items
from geodata.services.raster_loader import load_stack

job = MosaicJob.objects.select_related("roi").get(pk=35)
sensor = get_sensor_spec("sentinel-2-l2a")
items = search_items(job, sensor)
print("items:", len(items))
print("asset keys:", list(items[0].assets.keys()))
stack = load_stack(items[:1], job, sensor)
print("bands:", list(map(str, stack.coords["band"].values)))
```
