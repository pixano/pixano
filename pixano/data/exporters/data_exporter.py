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

from abc import ABC, abstractmethod
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import shortuuid

from pixano.data import DatasetInfo
from pixano.types import ObjectAnnotationType


class DataExporter(ABC):
    """Abstract Data Importer class

    Attributes:
        name (str): Dataset name
        description (str): Dataset description
        splits (list[str]): Dataset splits
        schema (pa.schema): Dataset schema
        partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
        views: list[pa.field],
    ):
        """Initialize Data Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
            views (list[pa.field]): Dataset views
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            num_elements=0,
            preview=None,
            categories=[],
            features={"split": "str", "id": "str", "objects": "[ObjectAnnotationType]"},
        )
        self.splits = splits

        # Dataset schema
        fields = [
            pa.field("split", pa.string()),
            pa.field("id", pa.string()),
            pa.field("objects", pa.list_(ObjectAnnotationType)),
        ]
        fields.extend(views)
        self.schema = pa.schema(fields)
        self.partitioning = ds.partitioning(
            pa.schema([("split", pa.string())]), flavor="hive"
        )

    @abstractmethod
    def export_dataset(self, input_dir: Path, export_dir: Path):
        """Export dataset back to original format

        Args:
            input_dir (Path): Input directory
            export_dir (Path): Export directory
        """

        pass
