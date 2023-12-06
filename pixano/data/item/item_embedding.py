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

import base64

import pyarrow as pa
from pydantic import BaseModel

from pixano.core import is_binary


class ItemEmbedding(BaseModel):
    """Embedding type for DatasetItem

    Attributes:
        view_id (str): Embedding view ID
        data (str): Embedding data in base 64
    """

    view_id: str
    data: str

    @staticmethod
    def from_pyarrow(table: pa.Table, schema: pa.schema) -> dict[str, "ItemEmbedding"]:
        """Create dictionary of ItemEmbedding from PyArrow Table

        Args:
            table (dict[str, Any]): PyArrow table
            schema (pa.schema): PyArrow schema

        Returns:
            dict[str, ItemEmbedding]: Dictionary of ItemEmbedding
        """

        item = table.to_pylist()[0]
        embeddings = {}

        # Iterate on fields
        for field in schema:
            # Image
            if is_binary(field.type):
                embeddings[field.name] = ItemEmbedding(
                    view_id=field.name,
                    data=base64.b64encode(item[field.name]).decode("ascii"),
                )

        return embeddings
