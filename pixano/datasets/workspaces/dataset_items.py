# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import (
    BBox,
    CompressedRLE,
    Conversation,
    Entity,
    Image,
    KeyPoints,
    Message,
    SequenceFrame,
    Track,
    Tracklet,
)

from ..dataset_schema import DatasetItem


class DefaultVQADatasetItem(DatasetItem):
    """Default VQA DatasetItem Schema."""

    image: Image
    conversations: list[Conversation]
    messages: list[Message]
    objects: list[Entity]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]


class DefaultVideoDatasetItem(DatasetItem):
    """Default Video DatasetItem Schema."""

    image: list[SequenceFrame]
    tracks: list[Track]
    tracklets: list[Tracklet]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]


class DefaultImageDatasetItem(DatasetItem):
    """Default Image DatasetItem Schema."""

    image: Image
    objects: list[Entity]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]
