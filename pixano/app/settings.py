# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from pydantic import ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings
from s3path import S3Path, register_configuration_parameter
from typing_extensions import Self


class Settings(BaseSettings):
    """Pixano app settings.

    Attributes:
        data_dir: Root data directory. If library_dir, media_dir, or models_dir are not provided,
            they are derived as data_dir/library, data_dir/media, and data_dir/models respectively.
        library_dir: Local or S3 path to dataset library. Overrides data_dir/library if provided.
        media_dir: Local or S3 path to media library. Overrides data_dir/media if provided.
        models_dir: Models directory as Path. Overrides data_dir/models if provided. Must be provided
            if library_dir is an S3 path.
        aws_endpoint: S3 endpoint URL, use 'AWS' if not provided.
            Used if library_dir is an S3 path.
        aws_region: S3 region name, not always required for private storages.
            Used if library_dir is an S3 path.
        aws_access_key: S3 AWS access key. Used if library_dir is an S3 path.
        aws_secret_key: S3 AWS secret key. Used if library_dir is an S3 path.
        inference_providers: Dictionary of connected inference providers (InferenceProvider instances),
            keyed by name.
        default_inference_provider: Name of the default inference provider to use.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_dir: Path | S3Path = Path.cwd()
    library_dir: Path | S3Path = Path.cwd() / "library"
    media_dir: Path | S3Path = Path.cwd() / "media"
    models_dir: Path | None = None
    aws_endpoint: str | None = None
    aws_region: str | None = None
    aws_access_key: str | None = None
    aws_secret_key: str | None = None
    inference_providers: dict[str, Any] = {}
    default_inference_provider: str | None = None

    @field_validator("data_dir", mode="before")
    @classmethod
    def _validate_before_data_dir(cls, data_dir: Any):
        if isinstance(data_dir, str):
            if urlparse(data_dir).scheme == "s3":
                return S3Path.from_uri(data_dir)
            return Path(data_dir)
        return data_dir

    @field_validator("library_dir", mode="before")
    @classmethod
    def _validate_before_library_dir(cls, library_dir: Any):
        if isinstance(library_dir, str):
            if urlparse(library_dir).scheme == "s3":
                library_dir = S3Path.from_uri(library_dir)
                return library_dir
            return Path(library_dir)
        return library_dir

    @field_validator("media_dir", mode="before")
    @classmethod
    def _validate_before_media_dir(cls, media_dir: Any):
        if isinstance(media_dir, str):
            if urlparse(media_dir).scheme == "s3":
                media_dir = S3Path.from_uri(media_dir)
                return media_dir
            return Path(media_dir)
        return media_dir

    @field_validator("models_dir", mode="before")
    @classmethod
    def _validate_before_model_dir(cls, models_dir: Any):
        if isinstance(models_dir, str):
            return Path(models_dir)
        return models_dir

    @model_validator(mode="after")
    def _validate_after_model(self) -> Self:
        # Derive library_dir, media_dir from data_dir if not explicitly provided
        if "library_dir" not in self.model_fields_set:
            self.library_dir = self.data_dir / "library"
        if "media_dir" not in self.model_fields_set:
            self.media_dir = self.data_dir / "media"

        # Setup library and media directories
        for attr in ["library_dir", "media_dir"]:
            if isinstance(getattr(self, attr), S3Path):
                try:
                    register_configuration_parameter(
                        getattr(self, attr),
                        resource=boto3.resource(
                            "s3",
                            endpoint_url=self.aws_endpoint,
                            region_name=self.aws_region,
                            aws_access_key_id=self.aws_access_key,
                            aws_secret_access_key=self.aws_secret_key,
                        ),
                    )
                except Exception as e:
                    raise ValueError(
                        f"ERROR: Could not register S3 {attr} library.\n"
                        "You have to set the following environment variables:\n"
                        "- AWS_ENDPOINT: S3 endpoint URL, use 'AWS' if not provided\n"
                        "- AWS_REGION: S3 region name, not always required "
                        "for private storages\n"
                        "- AWS_ACCESS_KEY: S3 AWS access key\n"
                        "- AWS_SECRET_KEY: S3 AWS secret key"
                    ) from e

        # Check if local model directory is provided
        if isinstance(self.library_dir, S3Path) and self.models_dir is None:
            raise AttributeError(
                "When using S3 storage for the library, runtime models (.onnx files) must be "
                "stored locally and their directory must be provided with 'model_dir'."
            )
        elif self.models_dir is None:
            self.models_dir = self.data_dir / "models"
        return self


@lru_cache
def get_settings() -> Settings:
    """Get app settings.

    Returns:
        App settings.
    """
    return Settings()
