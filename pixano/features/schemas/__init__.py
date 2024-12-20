# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .annotations import (
    Annotation,
    BaseIntrinsics,
    BBox,
    BBox3D,
    CamCalibration,
    Classification,
    CompressedRLE,
    Extrinsics,
    Intrinsics,
    KeyPoints,
    KeyPoints3D,
    Message,
    Relation,
    TextSpan,
    Tracklet,
    create_bbox,
    create_bbox3d,
    create_cam_calibration,
    create_classification,
    create_compressed_rle,
    create_keypoints,
    create_keypoints3d,
    create_message,
    create_relation,
    create_text_span,
    create_tracklet,
    is_annotation,
    is_bbox,
    is_bbox3d,
    is_cam_calibration,
    is_classification,
    is_compressed_rle,
    is_keypoints,
    is_keypoints3d,
    is_message,
    is_relation,
    is_text_span,
    is_tracklet,
)
from .base_schema import BaseSchema, is_base_schema
from .embeddings import Embedding, ViewEmbedding, create_view_embedding_function, is_embedding, is_view_embedding
from .entities import Conversation, Entity, Track, create_track, is_entity, is_track
from .items import Item, is_item
from .registry import register_schema
from .schema_group import SchemaGroup
from .source import Source, SourceKind, create_source, is_source
from .views import (
    Image,
    PointCloud,
    SequenceFrame,
    Text,
    Video,
    View,
    create_image,
    create_point_cloud,
    create_sequence_frame,
    create_text,
    create_video,
    is_image,
    is_point_cloud,
    is_sequence_frame,
    is_text,
    is_video,
    is_view,
)


__all__ = [
    "Annotation",
    "BaseIntrinsics",
    "BaseSchema",
    "BBox",
    "BBox3D",
    "CamCalibration",
    "Classification",
    "CompressedRLE",
    "Conversation",
    "Embedding",
    "Entity",
    "Extrinsics",
    "Image",
    "ImageObject",
    "Intrinsics",
    "Item",
    "KeyPoints",
    "KeyPoints3D",
    "Message",
    "TextSpan",
    "PointCloud",
    "Relation",
    "SchemaGroup",
    "SequenceFrame",
    "Source",
    "SourceKind",
    "Text",
    "Track",
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
    "create_image",
    "create_image_object",
    "create_keypoints",
    "create_keypoints3d",
    "create_text_span",
    "create_message",
    "create_point_cloud",
    "create_relation",
    "create_sequence_frame",
    "create_source",
    "create_text",
    "create_track",
    "create_tracklet",
    "create_video",
    "create_view_embedding_function",
    "is_annotation",
    "is_base_schema",
    "is_bbox",
    "is_bbox3d",
    "is_cam_calibration",
    "is_classification",
    "is_compressed_rle",
    "is_conversation",
    "is_embedding",
    "is_entity",
    "is_image",
    "is_item",
    "is_keypoints",
    "is_keypoints3d",
    "is_text_span",
    "is_message",
    "is_point_cloud",
    "is_relation",
    "is_sequence_frame",
    "is_source",
    "is_text",
    "is_track",
    "is_tracklet",
    "is_view",
    "is_video",
    "is_view_embedding",
    "register_schema",
]
