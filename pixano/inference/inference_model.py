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


class InferenceModel(ABC):
    """Abstract parent class for OfflineModel and OnlineModel

    Attributes:
        name (str): Model name
        id (str, optional): Model ID
        device (str, optional): Model GPU or CPU device
        source (str, optional): Model source
        info (str, optional): Additional model info
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        source: str = "",
        info: str = "",
    ) -> None:
        """Initialize model name and ID

        Args:
            name (str): Model name
            id (str, optional): Model ID. Defaults to "".
            device (str, optional): Model GPU or CPU device. Defaults to "".
            source (str, optional): Model source. Defaults to "".
            info (str, optional): Additional model info. Defaults to "".
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
    def __call__():
        """Call model"""

        pass

    @abstractmethod
    def process_dataset(
        self,
        input_dir: Path,
        views: list[str],
        splits: list[str] = [],
        batch_size: int = 1,
    ) -> Path:
        """Process parquet dataset

        Args:
            input_dir (Path): Input parquet location
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if []. Defaults to [].
            batch_size (int, optional): Rows per batch. Defaults to 1.

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
    ):
        """Save output .json

        Args:
            output_dir (Path): Output parquet location
            filename (str): Output .json filename
            spec_json (dict): Input parquet .json
            num_elements (int): Number of processed rows
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

        # Save .json
        with open(output_dir / f"{filename}.json", "w") as f:
            json.dump(output_json, f)
