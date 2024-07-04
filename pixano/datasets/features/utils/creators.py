# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import BaseModel

from pixano.datasets.features.schemas.base_schema import BaseSchema
from pixano.datasets.features.schemas.image import create_image, is_image
from pixano.datasets.features.schemas.image_object import create_image_object, is_image_object
from pixano.datasets.features.schemas.sequence_frame import create_sequence_frame, is_sequence_frame
from pixano.datasets.features.schemas.track_object import create_track_object, is_track_object
from pixano.datasets.features.schemas.tracklet import create_tracklet, is_tracklet
from pixano.datasets.features.schemas.video import create_video, is_video
from pixano.datasets.features.types.bbox import create_bbox, is_bbox
from pixano.datasets.features.types.bbox3d import create_bbox3d, is_bbox3d
from pixano.datasets.features.types.camcalibration import create_cam_calibration, is_cam_calibration
from pixano.datasets.features.types.compressed_rle import create_compressed_rle, is_compressed_rle
from pixano.datasets.features.types.keypoints import create_keypoints, is_keypoints
from pixano.datasets.features.types.keypoints3d import create_keypoints3d, is_keypoints3d
from pixano.datasets.features.types.nd_array_float import create_ndarray_float, is_ndarray_float


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

    elif is_track_object(schema, True):
        return create_track_object(**kwargs)

    elif is_image_object(schema, True):
        return create_image_object(**kwargs)

    else:
        return schema(**kwargs)


def create_pixano_object(object_type: type[BaseModel], **kwargs) -> BaseModel:
    """Create a pixano object."""
    if is_bbox(object_type, True):
        return create_bbox(**kwargs)

    elif is_bbox3d(object_type, True):
        return create_bbox3d(**kwargs)

    elif is_cam_calibration(object_type, True):
        return create_cam_calibration(**kwargs)

    elif is_compressed_rle(object_type, True):
        return create_compressed_rle(**kwargs)

    elif is_keypoints(object_type, True):
        return create_keypoints(**kwargs)

    elif is_keypoints3d(object_type, True):
        return create_keypoints3d(**kwargs)

    elif is_ndarray_float(object_type, True):
        return create_ndarray_float(**kwargs)

    else:
        raise ValueError(f"Object type {object_type} not supported.")
