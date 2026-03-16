# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from .bbox import BBox, BBox3D, create_bbox, create_bbox3d, is_bbox, is_bbox3d
from .classification import Classification, create_classification, is_classification
from .compressed_rle import CompressedRLE, create_compressed_rle, is_compressed_rle
from .conversation import Conversation, create_conversation, is_conversation
from .entity_annotation import AnnotationSourceKind, EntityAnnotation, is_entity_annotation
from .entity_group_annotation import EntityGroupAnnotation, is_entity_group_annotation
from .keypoints import KeyPoints, KeyPoints3D, create_keypoints, create_keypoints3d, is_keypoints, is_keypoints3d
from .message import Message, QuestionType, create_message, is_message
from .per_frame_annotation import PerFrameAnnotation, is_per_frame_annotation
from .relation import Relation, create_relation, is_relation
from .text_span import TextSpan, create_text_span, is_text_span
from .tracklet import Tracklet, is_tracklet


__all__ = [
    "AnnotationSourceKind",
    "EntityAnnotation",
    "EntityGroupAnnotation",
    "PerFrameAnnotation",
    "BBox",
    "BBox3D",
    "Classification",
    "CompressedRLE",
    "Conversation",
    "KeyPoints",
    "KeyPoints3D",
    "Message",
    "QuestionType",
    "Relation",
    "TextSpan",
    "Tracklet",
    "is_entity_annotation",
    "is_entity_group_annotation",
    "is_per_frame_annotation",
    "is_bbox",
    "is_bbox3d",
    "is_classification",
    "is_compressed_rle",
    "is_conversation",
    "is_keypoints",
    "is_keypoints3d",
    "is_message",
    "is_relation",
    "is_text_span",
    "is_tracklet",
    "create_bbox",
    "create_bbox3d",
    "create_classification",
    "create_compressed_rle",
    "create_conversation",
    "create_keypoints",
    "create_keypoints3d",
    "create_message",
    "create_relation",
    "create_text_span",
]
