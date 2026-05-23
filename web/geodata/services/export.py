from pathlib import Path

import rioxarray  # noqa: F401
from django.conf import settings
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

from geodata.services.bands import available_bands


def save_feature_stack_as_cog(data_array, output_name: str) -> Path:
    output_dir = settings.MEDIA_ROOT / "processing"
    output_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = output_dir / output_name
    cog_path = output_dir / output_name.replace(".tif", ".cog.tif")

    data_array = data_array.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=False)

    print("Exporting feature stack")
    print("dims:", data_array.dims)
    print("shape:", data_array.shape)
    print("bands:", available_bands(data_array))
    print("crs:", data_array.rio.crs)

    if data_array.rio.crs is None:
        raise ValueError("DataArray has no CRS. Check stackstac EPSG/CRS settings before export.")

    # Compute explicitly to make remote raster reading failures visible before COG conversion.
    data_array = data_array.compute()
    data_array.rio.to_raster(tmp_path)

    profile = cog_profiles.get("deflate")
    cog_translate(
        tmp_path,
        cog_path,
        profile,
        in_memory=False,
        quiet=True,
    )

    tmp_path.unlink(missing_ok=True)
    return cog_path
