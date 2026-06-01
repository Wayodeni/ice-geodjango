import xarray as xr
import rioxarray  # noqa: F401


def normalized_difference(a: xr.DataArray, b: xr.DataArray) -> xr.DataArray:
    return (a - b) / (a + b + 1e-6)


def require_bands(mosaic: xr.DataArray, required_bands: list[str]) -> None:
    available_bands = set(map(str, mosaic.coords["band"].values))
    missing_bands = [band for band in required_bands if band not in available_bands]

    if missing_bands:
        raise ValueError(
            f"Missing bands: {missing_bands}. "
            f"Available bands: {sorted(available_bands)}"
        )


def get_crs(mosaic: xr.DataArray):
    crs = mosaic.rio.crs

    if crs is not None:
        return crs

    if "crs" in mosaic.attrs:
        return mosaic.attrs["crs"]

    if "epsg" in mosaic.attrs:
        return f"EPSG:{mosaic.attrs['epsg']}"

    return None


def restore_rio_metadata(data_array: xr.DataArray, source: xr.DataArray) -> xr.DataArray:
    data_array = data_array.rio.set_spatial_dims(
        x_dim="x",
        y_dim="y",
        inplace=False,
    )

    crs = get_crs(source)
    if crs is not None:
        data_array = data_array.rio.write_crs(crs, inplace=False)

    transform = source.rio.transform(recalc=True)
    data_array = data_array.rio.write_transform(transform, inplace=False)

    return data_array


# def add_sentinel2_indices(mosaic: xr.DataArray) -> xr.DataArray:
#     require_bands(mosaic, ["B03", "B04", "B08", "B11"])

#     mosaic = mosaic.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=False)

#     green = mosaic.sel(band="B03")
#     red = mosaic.sel(band="B04")
#     nir = mosaic.sel(band="B08")
#     swir1 = mosaic.sel(band="B11")

#     ndsi = normalized_difference(green, swir1).assign_coords(band="NDSI")
#     ndvi = normalized_difference(nir, red).assign_coords(band="NDVI")
#     ndwi = normalized_difference(green, nir).assign_coords(band="NDWI")

#     indices = xr.concat([ndsi, ndvi, ndwi], dim="band")
#     result = xr.concat([mosaic, indices], dim="band")

#     return restore_rio_metadata(result, mosaic)

def add_sentinel2_indices(mosaic: xr.DataArray) -> xr.DataArray:
    return mosaic


def add_sentinel1_features(mosaic: xr.DataArray) -> xr.DataArray:
    keep_coords = {"band", "x", "y", "spatial_ref"}
    bad_coords = [c for c in mosaic.coords if c not in keep_coords]
    if bad_coords:
        mosaic = mosaic.drop_vars(bad_coords)
    require_bands(mosaic, ["vv", "vh"])

    mosaic = mosaic.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=False)

    vv = mosaic.sel(band="vv")
    vh = mosaic.sel(band="vh")

    ratio = (vv / (vh + 1e-6)).assign_coords(band="VV_VH_RATIO")

    result = xr.concat([mosaic, ratio], dim="band")
    return restore_rio_metadata(result, mosaic)


def create_feature_stack(mosaics: dict[str, xr.DataArray]) -> xr.DataArray:
    parts = []

    reference = None

    if "sentinel-2-l2a" in mosaics:
        reference = mosaics["sentinel-2-l2a"]
        parts.append(add_sentinel2_indices(mosaics["sentinel-2-l2a"]))

    if "sentinel-1-rtc" in mosaics:
        if reference is None:
            reference = mosaics["sentinel-1-rtc"]
        parts.append(add_sentinel1_features(mosaics["sentinel-1-rtc"]))

    if not parts:
        raise ValueError("No mosaics available for feature stack creation.")

    result = xr.concat(parts, dim="band")

    if reference is not None:
        result = restore_rio_metadata(result, reference)

    return result