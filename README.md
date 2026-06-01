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
```
