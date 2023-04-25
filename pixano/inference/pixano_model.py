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

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa


class PixanoModel(ABC):
    """Pixano abstract model class

    Args:
        name (str): Model name
        id (str): Model ID
        device (str): Model GPU or CPU device
        source (str): Model source
        info (str): Additional model info
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        source: str = "Not provided",
        info: str = "Not provided",
    ) -> None:
        """Initialize model name and ID

        Args:
            name (str): Model name
            id (str, optional): Use previously defined model by providing its ID. Defaults to "".
            device (str, optional): Device to run model on (e.g. "cuda" for PyTorch, "/GPU:0" for TensorFlow). Defaults to "".
            source (str, optional): Model source (e.g. "PyTorch Hub", "GitHub", "Local Model"). Defaults to "Not provided".
            info (str, optional): Any additional model info. Defaults to "Not provided".
        """

        self.name = name
        if id == "":
            self.id = f"{datetime.now().strftime('%y%m%d_%H%M%S')}_{name}"
        else:
            self.id = id
        self.device = device
        self.source = source
        self.info = info

    @abstractmethod
    def __call__(
        self,
        batch: pa.RecordBatch,
        view: str,
        media_dir: Path,
    ) -> Any:
        """Process batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            media_dir (Path): Media location

        Returns:
            Any: Processed batch
        """

        pass

    @abstractmethod
    def process_dataset(
        self,
        dataset_dir: Path,
        views: list[str],
        splits: list[str] = None,
        batch_size: int = 1,
    ) -> Path:
        """Process parquet dataset

        Args:
            input_dir (Path): Input parquet location
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if None. Defaults to None.
            batch size (int, optional): Rows per batch. Defaults to 1.

        Returns:
            Path: Output parquet location
        """

        pass

    def save_json(
        self,
        output_dir: Path,
        filename: str,
        spec_json: dict,
        num_elements: int,
        additional_info: dict = {},
    ):
        """Save output .json

        Args:
            output_dir (Path): Output parquet location
            filename (str): Output .json filename
            spec_json (dict): Input parquet .json
            num_elements (int): Number of processed rows
            additional_info (dict, optional): Additional info for output .json
        """

        # Load existing .json
        if (output_dir / f"{filename}.json").is_file():
            with open(output_dir / f"{filename}.json", "r") as f:
                output_json = json.load(f)
            output_json["num_elements"] += num_elements

        # Or create .json from scratch
        else:
            output_json = {
                "id": spec_json["id"],
                "name": spec_json["name"],
                "description": spec_json["description"],
                "num_elements": num_elements,
                "model_id": self.id,
                "model_name": self.name,
                "model_source": self.source,
                "model_info": self.info,
            }
            output_json.update(additional_info)

        # Save .json
        with open(output_dir / f"{filename}.json", "w") as f:
            json.dump(output_json, f)
