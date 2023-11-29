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

from typing import Optional

import pyarrow as pa
from pydantic import BaseModel

from pixano.core import is_number, is_string


class ItemFeature(BaseModel):
    """Feature

    Attributes:
        name (str): Feature name
        dtype (str): Feature type
        value (str | int | float | bool, optional): Feature value
    """

    name: str
    dtype: str
    value: Optional[str | int | float | bool] = None

    @staticmethod
    def from_pyarrow(
        table: pa.Table,
        schema: pa.schema,
    ) -> list["ItemFeature"]:
        """Create list of ItemFeature from PyArrow Table

        Args:
            table (pa.Table): PyArrow table
            schema (pa.schema): PyArrow schema

        Returns:
            list[ItemFeature]: List of ItemFeature
        """

        item = table.to_pylist()[0]
        features = []
        ignored_fields = ["id", "item_id", "view_id", "source_id", "split"]

        # Iterate on fields
        for field in schema:
            if field.name not in ignored_fields:
                # Number fields
                if is_number(field.type):
                    features.append(
                        ItemFeature(
                            name=field.name,
                            dtype="number",
                            value=item[field.name],
                        )
                    )
                # String fields
                elif is_string(field.type):
                    features.append(
                        ItemFeature(
                            name=field.name,
                            dtype="text",
                            value=item[field.name],
                        )
                    )

        return features
