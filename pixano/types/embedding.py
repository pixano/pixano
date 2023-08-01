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

import pyarrow as pa
from pydantic import BaseModel, PrivateAttr

from .all_pixano_types import PixanoType, createPaType

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class Embedding(PixanoType, BaseModel):
    _bytes: bytes = PrivateAttr()

    def __init__(self, bytes: bytes):
        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._bytes = bytes

    @property
    def bytes(self):
        return self._bytes

    @classmethod
    def to_struct(cls):
        return pa.struct([pa.field("bytes", pa.binary())])


EmbeddingType = createPaType(Embedding.to_struct(), "Embedding", Embedding)
