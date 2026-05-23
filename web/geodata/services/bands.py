"""Helpers for stable band naming across STAC providers."""

SENTINEL2_TO_INTERNAL = {
    "blue": "B02",
    "green": "B03",
    "red": "B04",
    "nir": "B08",
    "nir08": "B08",
    "swir16": "B11",
    "swir22": "B12",
    "scl": "SCL",
    "SCL": "SCL",
    "B02": "B02",
    "B03": "B03",
    "B04": "B04",
    "B08": "B08",
    "B11": "B11",
    "B12": "B12",
}

SENTINEL1_TO_INTERNAL = {
    "vv": "vv",
    "vh": "vh",
    "VV": "vv",
    "VH": "vh",
}


def normalize_band_names(data_array, sensor_name: str):
    if "band" not in data_array.coords:
        return data_array

    if sensor_name == "sentinel-2-l2a":
        rename_map = SENTINEL2_TO_INTERNAL
    elif sensor_name == "sentinel-1-rtc":
        rename_map = SENTINEL1_TO_INTERNAL
    else:
        rename_map = {}

    normalized = [rename_map.get(str(value), str(value)) for value in data_array.coords["band"].values]
    return data_array.assign_coords(band=normalized)


def available_bands(data_array) -> list[str]:
    if "band" not in data_array.coords:
        return []
    return list(map(str, data_array.coords["band"].values))


def require_bands(data_array, required_bands: list[str]) -> None:
    available = set(available_bands(data_array))
    missing = [band for band in required_bands if band not in available]

    if missing:
        raise ValueError(
            f"Missing bands: {missing}. Available bands: {sorted(available)}. "
            "Check sensor_registry.py and band normalization."
        )
