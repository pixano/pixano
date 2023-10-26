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
from pydantic import BaseModel

from pixano.core.bbox import BBox, BBoxType
from pixano.core.pixano_type import PixanoType, create_pyarrow_type


class GtInfo(PixanoType, BaseModel):
    """GtInfo type

    Attributes:
        bbox_obj (BBox): bbox_obj
        bbox_visib (BBox): bbox_visib
        px_count_all (int): px_count_all
        px_count_valid (int): px_count_valid
        px_count_visib (int): px_count_visib
        visib_fract (float): visib_fract
    """

    bbox_obj: BBox
    bbox_visib: BBox
    px_count_all: int
    px_count_valid: int
    px_count_visib: int
    visib_fract: float

    def __init__(
        self,
        bbox_obj: BBox,
        bbox_visib: BBox,
        px_count_all: int,
        px_count_valid: int,
        px_count_visib: int,
        visib_fract: float,
    ):
        """Initialize GtInfo

        Args:
            bbox_obj (BBox): bbox_obj
            bbox_visib (BBox): bbox_visib
            px_count_all (int): px_count_all
            px_count_valid (int): px_count_valid
            px_count_visib (int): px_count_visib
            visib_fract (float): visib_fract
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            bbox_obj=bbox_obj,
            bbox_visib=bbox_visib,
            px_count_all=px_count_all,
            px_count_valid=px_count_valid,
            px_count_visib=px_count_visib,
            visib_fract=visib_fract,
        )

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return GtInfo type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("bbox_obj", BBoxType),
                pa.field("bbox_visib", BBoxType),
                pa.field("px_count_all", pa.int64()),
                pa.field("px_count_valid", pa.int64()),
                pa.field("px_count_visib", pa.int64()),
                pa.field("visib_fract", pa.float64()),
            ]
        )


GtInfoType = create_pyarrow_type(GtInfo.to_struct(), "GtInfo", GtInfo)
