# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing_extensions import TYPE_CHECKING


if TYPE_CHECKING:
    from pixano.features.schemas import BaseSchema
    from pixano.features.types import BaseType


def create_instance_of_schema(schema: type["BaseSchema"], **data) -> "BaseSchema":
    """Create a row in a Schema."""
    # Import here to avoid circular imports
    from pixano.features.schemas import (
        create_bbox,
        create_bbox3d,
        create_cam_calibration,
        create_compressed_rle,
        create_image,
        create_keypoints,
        create_keypoints3d,
        create_sequence_frame,
        create_track,
        create_tracklet,
        create_video,
        is_base_schema,
        is_bbox,
        is_bbox3d,
        is_cam_calibration,
        is_compressed_rle,
        is_image,
        is_keypoints,
        is_keypoints3d,
        is_sequence_frame,
        is_track,
        is_tracklet,
        is_video,
    )

    if is_image(schema, strict=True):
        return create_image(**data)

    elif is_video(schema, strict=True):
        return create_video(**data)

    elif is_sequence_frame(schema, strict=True):
        return create_sequence_frame(**data)

    elif is_tracklet(schema, strict=True):
        return create_tracklet(**data)

    elif is_track(schema, True):
        return create_track(**data)

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

    elif is_base_schema(schema, False):
        return schema(**data)

    raise ValueError(f"Schema {schema} is not a base schema.")


def create_instance_of_pixano_type(pix_type: type["BaseType"], **data) -> "BaseType":
    """Create a pixano object."""
    # Import here to avoid circular imports
    from pixano.features.types import (
        create_annotation_ref,
        create_embedding_ref,
        create_entity_ref,
        create_item_ref,
        create_ndarray_float,
        create_schema_ref,
        create_source_ref,
        create_view_ref,
        is_annotation_ref,
        is_base_type,
        is_embedding_ref,
        is_entity_ref,
        is_item_ref,
        is_ndarray_float,
        is_schema_ref,
        is_source_ref,
        is_view_ref,
    )

    if is_ndarray_float(pix_type, True):
        return create_ndarray_float(**data)

    elif is_schema_ref(pix_type, True):
        return create_schema_ref(**data)

    elif is_item_ref(pix_type, True):
        return create_item_ref(**data)

    elif is_view_ref(pix_type, True):
        return create_view_ref(**data)

    elif is_entity_ref(pix_type, True):
        return create_entity_ref(**data)

    elif is_annotation_ref(pix_type, True):
        return create_annotation_ref(**data)

    elif is_embedding_ref(pix_type, True):
        return create_embedding_ref(**data)

    elif is_source_ref(pix_type, True):
        return create_source_ref(**data)

    elif is_base_type(pix_type, False):
        return pix_type(**data)

    raise ValueError(f"Type {pix_type} not supported.")
