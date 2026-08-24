import math
import re

from django.core.exceptions import ValidationError
from pyproj import CRS
from pyproj.exceptions import CRSError

from geodata.services.sensor_registry import (
    SENSOR_REGISTRY,
    allowed_resolutions_for,
)


EPSG_PATTERN = re.compile(r"^EPSG:(\d+)$", re.IGNORECASE)


def normalize_and_validate_job_settings(selected_sensors, target_crs, resolution):
    if not isinstance(selected_sensors, list) or not selected_sensors:
        raise ValidationError({"selected_sensors": "Select at least one sensor."})

    unsupported = sorted(set(selected_sensors) - set(SENSOR_REGISTRY))
    if unsupported:
        raise ValidationError({
            "selected_sensors": f"Unsupported sensors: {', '.join(unsupported)}."
        })

    if len(selected_sensors) != len(set(selected_sensors)):
        raise ValidationError({"selected_sensors": "Sensors must not be duplicated."})

    crs_value = str(target_crs or "").strip().upper()
    match = EPSG_PATTERN.fullmatch(crs_value)
    if not match:
        raise ValidationError({"target_crs": "Use an EPSG code, for example EPSG:32643."})

    try:
        crs = CRS.from_epsg(int(match.group(1)))
    except CRSError:
        raise ValidationError({"target_crs": f"Unknown CRS: {crs_value}."})

    if not crs.is_projected:
        raise ValidationError({
            "target_crs": "Target CRS must be projected; geographic CRS is not supported."
        })

    horizontal_axes = crs.axis_info[:2]
    if len(horizontal_axes) < 2 or any(
        (axis.unit_name or "").lower() not in {"metre", "meter"}
        or not math.isclose(axis.unit_conversion_factor, 1.0)
        for axis in horizontal_axes
    ):
        raise ValidationError({
            "target_crs": "Target CRS must use metres as its horizontal units."
        })

    try:
        resolution_value = float(resolution)
    except (TypeError, ValueError):
        raise ValidationError({"resolution": "Resolution must be a number."})

    allowed_resolutions = allowed_resolutions_for(selected_sensors)
    if not math.isfinite(resolution_value) or resolution_value not in allowed_resolutions:
        allowed = ", ".join(str(value) for value in allowed_resolutions)
        raise ValidationError({
            "resolution": f"Allowed resolution for the selected sensors: {allowed} m."
        })

    return {
        "selected_sensors": selected_sensors,
        "target_crs": crs_value,
        "resolution": resolution_value,
    }
