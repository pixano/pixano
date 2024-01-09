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

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import boto3
from pydantic_settings import BaseSettings
from s3path import S3Path, register_configuration_parameter


class Settings(BaseSettings):
    """Dataset library settings

    Attributes:
        data_dir (Path | S3Path): Dataset library directory, or url to S3 path
        aws_endpoint (str, optional): S3 compatible storage url. Used if data_dir is a S3 path. Use AWS if not provided
        aws_access_key_id (str, optional): Access key. Used if data_dir is a S3 path
        aws_secret_access_key (str, optional): Secret key. Used if data_dir is a S3 path
        aws_region (str, optional): Region. Used if data_dir is a S3 path. Not always required for private S3 storages
        local_model_dir (str, optional): Path to model (local). Required if data_dir is a S3 path
    """

    data_dir: Path | S3Path = Path.cwd() / "library"

    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    aws_endpoint: Optional[str] = None
    local_model_dir: Optional[Path] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if urlparse(str(self.data_dir)).scheme == "s3":
            try:
                aws_ressource = boto3.resource(
                    "s3",
                    region_name=self.aws_region,
                    endpoint_url=self.aws_endpoint,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                )
                self.data_dir = S3Path.from_uri(
                    str(self.data_dir).replace("s3:/", "s3://")
                )
                register_configuration_parameter(self.data_dir, resource=aws_ressource)
            except Exception as e:
                raise ValueError(
                    "ERROR Could not register S3 compatible storage.\n"
                    "You have to set the following environment variables:\n"
                    "- AWS_ENDPOINT : S3 Compatible Storage endpoint\n"
                    "- AWS_ACCESS_KEY_ID : access key credentials\n"
                    "- AWS_SECRET_ACCESS_KEY : secret access credentials\n"
                    "- AWS_REGION (optionnal)"
                ) from e
            # if S3, local_model_dir have to be set (maybe we could download it from S3 into a defined local dir?)
            if self.local_model_dir is None:
                raise AttributeError(
                    "Runtime model (.onnx) must be local, LOCAL_MODEL_DIR must be provided"
                )
