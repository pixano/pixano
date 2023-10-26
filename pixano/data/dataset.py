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

import lancedb

from pixano.data.dataset_info import DatasetInfo


class Dataset:
    """Dataset class

    Attributes:
        _path (Path): Dataset path
        _info (DatasetInfo): Dataset info
    """

    def __init__(self, path: Path):
        """Initialize dataset

        Args:
            path (Path): Dataset path
        """

        self._path = path
        self._info = DatasetInfo.parse_file(self._path / "db.json")

    @property
    def info(self) -> DatasetInfo:
        """Return Dataset info

        Returns:
            DatasetInfo: Dataset info
        """

        return self._info

    @property
    def path(self) -> Path:
        """Return Dataset path

        Returns:
            Path: Dataset path
        """

        return self._path

    @property
    def media_dir(self) -> Path:
        """Return Dataset media directory

        Returns:
            Path: Dataset media directory
        """

        return self._path / "media"

    def connect(self) -> lancedb.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.DBConnection: Dataset LanceDB connection
        """

        return lancedb.connect(self._path)

    def save_info(self):
        """Save dataset info to file"""

        self.info.save(self.path)
