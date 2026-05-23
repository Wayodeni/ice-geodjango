from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    name: str
    collection: str
    bands: list[str]
    is_optical: bool
    cloud_property: str | None = None


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
    ),
    "sentinel-1-rtc": SensorSpec(
        name="sentinel-1-rtc",
        collection="sentinel-1-rtc",
        bands=["vv", "vh"],
        is_optical=False,
        cloud_property=None,
    ),
}


def get_sensor_spec(sensor_name: str) -> SensorSpec:
    if sensor_name not in SENSOR_REGISTRY:
        raise ValueError(f"Unsupported sensor: {sensor_name}")
    return SENSOR_REGISTRY[sensor_name]
