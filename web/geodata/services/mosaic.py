import xarray as xr


def build_median_mosaic(stack: xr.DataArray) -> xr.DataArray:
    return stack.median(dim="time", skipna=True)


def build_closest_date_mosaic(stack: xr.DataArray, target_date) -> xr.DataArray:
    target = xr.DataArray(target_date.isoformat()).astype("datetime64[ns]")
    time_distance = abs(stack.time - target)
    closest_index = int(time_distance.argmin().values)
    return stack.isel(time=closest_index)


def build_optical_mosaic(stack: xr.DataArray) -> xr.DataArray:
    return build_median_mosaic(stack)


def build_sar_mosaic(stack: xr.DataArray) -> xr.DataArray:
    return build_median_mosaic(stack)
