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

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class Embedding:
    def __init__(self, embedding_bytes: bytes) -> None:
        self._embedding_bytes = embedding_bytes

    def to_dict(self) -> dict:
        return {"embedding_bytes": self._embedding_bytes}


# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------


class EmbeddingType(pa.ExtensionType):
    """Embedding type as PyArrow binary"""

    def __init__(self):
        super(EmbeddingType, self).__init__(
            pa.struct([pa.field("bytes", pa.binary())]), "embedding"
        )

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return EmbeddingType()

    def __arrow_ext_serialize__(self):
        return b""

    def __arrow_ext_scalar_class__(self):
        return EmbeddingScalar

    def __arrow_ext_class__(self):
        return EmbeddingArray


class EmbeddingScalar(pa.ExtensionScalar):
    def as_py(self) -> Embedding:
        return Embedding(self.value["bytes"].as_py())


class EmbeddingArray(pa.ExtensionArray):
    """Class to use pa.array for Embedding instance"""

    @classmethod
    def from_Embedding_list(cls, embedding_list: list[Embedding]) -> pa.Array:
        """Create Embedding pa.array from embedding list

        Args:
            embedding_list (list[Bbox]): list of embedding

        Returns:
            pa.Array: pa.array of Embedding
        """
        embedding_dicts = [embedding.to_dict() for embedding in embedding_list]

        return pa.array(embedding_dicts, EmbeddingType())


def is_embedding_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of EmbeddingType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """

    return isinstance(t, EmbeddingType)
