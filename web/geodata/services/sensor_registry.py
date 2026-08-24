from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    name: str
    collection: str
    bands: list[str]
    is_optical: bool
    cloud_property: str | None = None
    allowed_resolutions: tuple[int, ...] = (10,)


SENSOR_REGISTRY = {
    "sentinel-2-l2a": SensorSpec(
        name="sentinel-2-l2a",
        collection="sentinel-2-l2a",
        # Planetary Computer Sentinel-2 L2A usually exposes ESA-style asset keys.
        # The processing pipeline normalizes possible common names such as red/green/blue
        # to these internal names after loading.
        bands=["B02", "B03", "B04", "SCL"],
        is_optical=True,
        cloud_property="eo:cloud_cover",
        allowed_resolutions=(10, 20, 60),
    ),
    "sentinel-1-rtc": SensorSpec(
        name="sentinel-1-rtc",
        collection="sentinel-1-rtc",
        bands=["vv", "vh"],
        is_optical=False,
        cloud_property=None,
        allowed_resolutions=(10,),
    ),
}


def get_sensor_spec(sensor_name: str) -> SensorSpec:
    if sensor_name not in SENSOR_REGISTRY:
        raise ValueError(f"Unsupported sensor: {sensor_name}")
    return SENSOR_REGISTRY[sensor_name]


def allowed_resolutions_for(sensor_names) -> tuple[int, ...]:
    """Return resolutions supported by every selected sensor."""
    supported = None
    for sensor_name in sensor_names:
        resolutions = set(get_sensor_spec(sensor_name).allowed_resolutions)
        supported = resolutions if supported is None else supported & resolutions
    return tuple(sorted(supported or ()))
