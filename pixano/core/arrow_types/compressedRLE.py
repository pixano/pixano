# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purcompressedRLE is to
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


class CompressedRLE:
    def __init__(self, size: list[float], counts: bytes):
        self._size = size
        self._counts = counts

    @property
    def size(self) -> list[float]:
        return self._size

    @property
    def counts(self) -> bytes:
        return self._counts

    def to_dict(self) -> dict[list[float], bytes]:
        """convert compressedRLE to dict

        Returns:
            dict[list[float], list[float]]: dict containing "size" and "counts"
        """
        return {"size": self.size, "counts": self.counts}


# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------


class CompressedRLEType(pa.ExtensionType):
    """Segmentation mask type as PyArrow StructType"""

    def __init__(self):
        super(CompressedRLEType, self).__init__(
            pa.struct(
                [
                    pa.field("size", pa.list_(pa.int32(), list_size=2)),
                    pa.field("counts", pa.binary()),
                ]
            ),
            "mask[rle]",
        )

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return CompressedRLEType()

    def __arrow_ext_serialize__(self):
        return b""

    def __arrow_ext_scalar_class__(self):
        return CompressedRLEScalar

    def __arrow_ext_class__(self):
        return CompressedRLEArray


class CompressedRLEScalar(pa.ExtensionScalar):
    def as_py(self) -> CompressedRLE:
        return CompressedRLE(self.value["size"].as_py(), self.value["counts"].as_py())


class CompressedRLEArray(pa.ExtensionArray):
    """Class to use pa.array for CompressedRLE instance"""

    @classmethod
    def from_CompressedRLE_list(
        cls, compressedRLE_list: list[CompressedRLE]
    ) -> pa.Array:
        """Create CompressedRLE pa.array from compressedRLE list

        Args:
            compressedRLE_list (list[compressedRLE]): list of compressedRLE

        Returns:
            pa.Array: pa.array of CompressedRLE
        """
        compressedRLE_dicts = [
            compressedRLE.to_dict() for compressedRLE in compressedRLE_list
        ]

        return pa.array(compressedRLE_dicts, CompressedRLEType())


def is_compressedRLE_type(t: pa.DataType) -> bool:
    """Returns True if value is an instance of CompressedRLEType

    Args:
        t (pa.DataType): Value to check

    Returns:
        bool: Type checking response
    """

    return isinstance(t, CompressedRLEType)
