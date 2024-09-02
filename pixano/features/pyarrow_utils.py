# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pyarrow as pa


SERIALIZE_PYARROW_DATATYPE = {
    pa.float16(): "halffloat",
    pa.float32(): "float",
    pa.float64(): "double",
    pa.int8(): "int8",
    pa.int16(): "int16",
    pa.int32(): "int32",
    pa.int64(): "int64",
    pa.uint8(): "uint8",
    pa.uint16(): "uint16",
    pa.uint32(): "uint32",
    pa.uint64(): "uint64",
    pa.binary(): "binary",
    pa.bool_(): "bool",
}

DESERIALIZE_PYARROW_DATATYPE = {v: k for k, v in SERIALIZE_PYARROW_DATATYPE.items()}
