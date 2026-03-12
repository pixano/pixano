# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel
from pydantic import BaseModel


def create_instance_of_schema(schema: type[LanceModel], **data) -> LanceModel:
    """Create a row in a Schema."""
    # Import here to avoid circular imports
    from pixano.schemas import (
        Image,
        SequenceFrame,
        create_bbox,
        create_bbox3d,
        create_cam_calibration,
        create_compressed_rle,
        create_keypoints,
        create_keypoints3d,
        create_pdf,
        create_video,
        is_bbox,
        is_bbox3d,
        is_cam_calibration,
        is_compressed_rle,
        is_image,
        is_keypoints,
        is_keypoints3d,
        is_pdf,
        is_sequence_frame,
        is_tracklet,
        is_video,
    )

    if is_image(schema, strict=True):
        return Image.from_bytes(**data)

    elif is_video(schema, strict=True):
        # create_video does not accept raw_bytes; filter it out
        video_data = {k: v for k, v in data.items() if k != "raw_bytes"}
        return create_video(**video_data)

    elif is_sequence_frame(schema, strict=True):
        return SequenceFrame.from_bytes(**data)

    elif is_pdf(schema, strict=True):
        return create_pdf(**data)

    elif is_tracklet(schema, strict=True):
        # No dedicated create_tracklet factory; delegate to schema constructor
        return schema(**data)

    elif is_bbox(schema, True):
        return create_bbox(**data)

    elif is_bbox3d(schema, True):
        return create_bbox3d(**data)

    elif is_cam_calibration(schema, True):
        return create_cam_calibration(**data)

    elif is_compressed_rle(schema, True):
        return create_compressed_rle(**data)

    elif is_keypoints(schema, True):
        return create_keypoints(**data)

    elif is_keypoints3d(schema, True):
        return create_keypoints3d(**data)

    elif issubclass(schema, LanceModel):
        return schema(**data)

    raise ValueError(f"Schema {schema} is not a LanceModel subclass.")


def create_instance_of_pixano_type(pix_type: type[BaseModel], **data) -> BaseModel:
    """Create a pixano object."""
    # Import here to avoid circular imports
    from pixano.features.types import (
        create_ndarray_float,
        is_ndarray_float,
    )

    if is_ndarray_float(pix_type, True):
        return create_ndarray_float(**data)

    elif issubclass(pix_type, BaseModel):
        return pix_type(**data)

    raise ValueError(f"Type {pix_type} not supported.")
