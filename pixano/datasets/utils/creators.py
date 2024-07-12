# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.base_schema import is_base_schema

from ..features import (
    BaseSchema,
    BaseType,
    create_annotation_ref,
    create_bbox,
    create_bbox3d,
    create_cam_calibration,
    create_compressed_rle,
    create_embedding_ref,
    create_entity_ref,
    create_image,
    create_item_ref,
    create_keypoints,
    create_keypoints3d,
    create_ndarray_float,
    create_schema_ref,
    create_sequence_frame,
    create_track,
    create_tracklet,
    create_video,
    create_view_ref,
    is_annotation_ref,
    is_base_type,
    is_bbox,
    is_bbox3d,
    is_cam_calibration,
    is_compressed_rle,
    is_embedding_ref,
    is_entity_ref,
    is_image,
    is_item_ref,
    is_keypoints,
    is_keypoints3d,
    is_ndarray_float,
    is_schema_ref,
    is_sequence_frame,
    is_track,
    is_tracklet,
    is_video,
    is_view_ref,
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

    elif is_base_schema(schema, False):
        return schema(**kwargs)

    raise ValueError(f"Schema {schema} is not a base schema.")


def create_pixano_object(pix_type: type[BaseType], **kwargs) -> BaseType:
    """Create a pixano object."""
    if is_ndarray_float(pix_type, True):
        return create_ndarray_float(**kwargs)

    elif is_schema_ref(pix_type, True):
        return create_schema_ref(**kwargs)

    elif is_item_ref(pix_type, True):
        return create_item_ref(**kwargs)

    elif is_view_ref(pix_type, True):
        return create_view_ref(**kwargs)

    elif is_entity_ref(pix_type, True):
        return create_entity_ref(**kwargs)

    elif is_annotation_ref(pix_type, True):
        return create_annotation_ref(**kwargs)

    elif is_embedding_ref(pix_type, True):
        return create_embedding_ref(**kwargs)

    elif is_base_type(pix_type, False):
        return pix_type(**kwargs)

    raise ValueError(f"Type {pix_type} not supported.")
