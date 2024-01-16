# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import boto3
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from s3path import S3Path, register_configuration_parameter


class Settings(BaseSettings):
    """Pixano app settings

    Attributes:
        library_dir (str): Local or S3 path to dataset library
        endpoint_url (str): S3 endpoint URL, use 'AWS' if not provided. Used if library_dir is an S3 path
        region_name (str): S3 region name, not always required for private storages. Used if library_dir is an S3 path
        aws_access_key (str): S3 AWS access key. Used if library_dir is an S3 path
        aws_secret_key (str): S3 AWS secret key. Used if library_dir is an S3 path
        local_model_dir (str): Local path to models. Used if library_dir is an S3 path
        data_dir (Path | S3Path): Dataset directory as Path | S3Path
        model_dir (Path): Model directory as Path
    """

    library_dir: Optional[str] = (Path.cwd() / "library").as_posix()
    endpoint_url: Optional[str] = None
    region_name: Optional[str] = None
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    local_model_dir: Optional[str] = None
    data_dir: Optional[Path | S3Path] = None
    model_dir: Optional[Path] = None
    # Change Pydantic protected namespace from "model_" to "settings_" because of model_dir
    model_config = ConfigDict(protected_namespaces=("settings_",))

    def __init__(self, *args, **kwargs):
        """Initialize settings"""

        super().__init__(*args, **kwargs)

        # Setup data directory
        if urlparse(self.library_dir).scheme == "s3":
            # S3 library
            try:
                self.data_dir = S3Path.from_uri(self.library_dir)
                register_configuration_parameter(
                    self.data_dir,
                    resource=boto3.resource(
                        "s3",
                        endpoint_url=self.endpoint_url,
                        region_name=self.region_name,
                        aws_access_key_id=self.aws_access_key,
                        aws_secret_access_key=self.aws_secret_key,
                    ),
                )
            except Exception as e:
                raise ValueError(
                    "ERROR: Could not register S3 dataset library.\n"
                    "You have to set the following environment variables:\n"
                    "- ENDPOINT_URL: S3 endpoint URL, use 'AWS' if not provided\n"
                    "- AWS_REGION: S3 region name, not always required for private storages\n"
                    "- AWS_ACCESS_KEY: S3 AWS access key\n"
                    "- AWS_SECRET_KEY: S3 AWS secret key"
                ) from e

            # Check if local model directory is provided
            if self.local_model_dir is None:
                raise AttributeError(
                    "When using S3 storage, runtime models (.onnx files) must be stored locally and their directory must be provided with LOCAL_MODEL_DIR."
                )
            self.model_dir = Path(self.local_model_dir)

        else:
            # Local library
            self.data_dir = Path(self.library_dir)
            self.model_dir = self.data_dir / "models"


@lru_cache
def get_settings() -> Settings:
    """Get app settings

    Returns:
        Settings: App settings
    """

    return Settings()
