import numpy as np
import xarray as xr

from geodata.services.bands import available_bands, require_bands

SENTINEL2_CLEAR_SCL_CLASSES = [4, 5, 6, 7, 11]


def mask_sentinel2(stack: xr.DataArray) -> xr.DataArray:
    if "SCL" not in available_bands(stack):
        print("Sentinel-2 SCL band is not available. Cloud/shadow mask skipped.")
        return stack

    scl = stack.sel(band="SCL")
    valid_mask = xr.apply_ufunc(
        np.isin,
        scl,
        SENTINEL2_CLEAR_SCL_CLASSES,
        dask="allowed",
    )
    spectral = stack.sel(band=[band for band in stack.band.values if str(band) != "SCL"])
    return spectral.where(valid_mask)


def mask_sentinel1(stack: xr.DataArray) -> xr.DataArray:
    require_bands(stack, ["vv", "vh"])
    valid = np.isfinite(stack)
    valid = valid & (stack > -50) & (stack < 5)
    return stack.where(valid)


def apply_masks(stack: xr.DataArray, sensor_name: str) -> xr.DataArray:
    if sensor_name == "sentinel-2-l2a":
        return mask_sentinel2(stack)
    if sensor_name == "sentinel-1-rtc":
        return mask_sentinel1(stack)
    return stack
