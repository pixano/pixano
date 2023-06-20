import pyarrow as pa


class Embedding:
    def __init__(self, embedding) -> None:
        self._embedding = embedding

    def to_dict(self) -> dict[bytes]:
        return {"embedding": self._embedding}


class EmbeddingType(pa.ExtensionType):
    """Embedding type as PyArrow binary"""

    def __init__(self):
        super(EmbeddingType, self).__init__(pa.binary(), "embedding")

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
        return Embedding(self.value["embedding"].as_py())


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
