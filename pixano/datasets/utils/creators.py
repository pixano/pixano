# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from ..features import (
    BaseSchema,
    BaseType,
    create_bbox,
    create_bbox3d,
    create_cam_calibration,
    create_compressed_rle,
    create_image,
    create_keypoints,
    create_keypoints3d,
    create_ndarray_float,
    create_sequence_frame,
    create_track,
    create_tracklet,
    create_video,
    is_bbox,
    is_bbox3d,
    is_cam_calibration,
    is_compressed_rle,
    is_image,
    is_keypoints,
    is_keypoints3d,
    is_ndarray_float,
    is_sequence_frame,
    is_track,
    is_tracklet,
    is_video,
)


def create_row(schema: type[BaseSchema], **kwargs) -> BaseSchema:
    """Create a row in a Schema."""
    if is_image(schema, strict=True):
        return create_image(**kwargs)

    elif is_video(schema, strict=True):
        return create_video(**kwargs)

    elif is_sequence_frame(schema, strict=True):
        return create_sequence_frame(**kwargs)

    elif is_tracklet(schema, strict=True):
        return create_tracklet(**kwargs)

    elif is_track(schema, True):
        return create_track(**kwargs)

    elif is_bbox(schema, True):
        return create_bbox(**kwargs)

    elif is_bbox3d(schema, True):
        return create_bbox3d(**kwargs)

    elif is_cam_calibration(schema, True):
        return create_cam_calibration(**kwargs)

    elif is_compressed_rle(schema, True):
        return create_compressed_rle(**kwargs)

    elif is_keypoints(schema, True):
        return create_keypoints(**kwargs)

    elif is_keypoints3d(schema, True):
        return create_keypoints3d(**kwargs)

    else:
        return schema(**kwargs)


def create_pixano_object(pix_type: type[BaseType], **kwargs) -> BaseType:
    """Create a pixano object."""
    if is_ndarray_float(pix_type, True):
        return create_ndarray_float(**kwargs)

    else:
        raise ValueError(f"Pixano type {pix_type} not supported.")
