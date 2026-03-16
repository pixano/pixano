# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .pyarrow_utils import DESERIALIZE_PYARROW_DATATYPE, SERIALIZE_PYARROW_DATATYPE


_SCHEMA_EXPORTS = {
    "AnnotationSourceKind",
    "PerFrameAnnotation",
    "BaseIntrinsics",
    "BBox",
    "BBox3D",
    "CamCalibration",
    "CANONICAL_SCHEMA_MAP",
    "Classification",
    "CompressedRLE",
    "Conversation",
    "Embedding",
    "Entity",
    "EntityDynamicState",
    "Extrinsics",
    "Image",
    "Intrinsics",
    "KeyPoints",
    "KeyPoints3D",
    "Message",
    "QuestionType",
    "PDF",
    "PointCloud",
    "PointCloudFrame",
    "Record",
    "RecordComponent",
    "Relation",
    "SchemaGroup",
    "SequenceFrame",
    "Text",
    "TextSpan",
    "Tracklet",
    "Video",
    "View",
    "ViewEmbedding",
    "create_bbox",
    "create_bbox3d",
    "create_cam_calibration",
    "create_classification",
    "create_compressed_rle",
    "create_conversation",
    "create_keypoints",
    "create_keypoints3d",
    "create_message",
    "create_pdf",
    "create_point_cloud",
    "create_point_cloud_frame",
    "create_relation",
    "create_text",
    "create_text_span",
    "create_video",
    "create_view_embedding_function",
    "canonical_table_name_for_schema",
    "canonical_table_name_for_slot",
    "canonical_table_name_for_view_schema",
    "group_to_str",
    "is_bbox",
    "is_bbox3d",
    "is_cam_calibration",
    "is_classification",
    "is_compressed_rle",
    "is_conversation",
    "is_embedding",
    "is_entity",
    "is_entity_dynamic_state",
    "is_image",
    "is_keypoints",
    "is_keypoints3d",
    "is_message",
    "is_pdf",
    "is_per_frame_annotation",
    "is_point_cloud",
    "is_point_cloud_frame",
    "is_record",
    "is_record_component",
    "is_relation",
    "is_supported_view_schema",
    "is_sequence_frame",
    "is_text",
    "is_text_span",
    "is_tracklet",
    "is_video",
    "is_view",
    "is_view_embedding",
    "schema_to_group",
    "supported_dataset_info_slots",
}

_TYPE_EXPORTS = {
    "NDArrayFloat",
    "create_ndarray_float",
    "is_ndarray_float",
}

__all__ = [
    "DESERIALIZE_PYARROW_DATATYPE",
    "SERIALIZE_PYARROW_DATATYPE",
    *_SCHEMA_EXPORTS,
    *_TYPE_EXPORTS,
]


def __getattr__(name: str):
    if name in _SCHEMA_EXPORTS:
        from pixano import schemas as _schemas

        return getattr(_schemas, name)
    if name in _TYPE_EXPORTS:
        from . import types as _types

        return getattr(_types, name)
    raise AttributeError(f"module 'pixano.features' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
