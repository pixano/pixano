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

    # TODO will be added soon... (but need some rework to allow both Conversation and Entity)
    # bboxes: list[BBox]
    # masks: list[CompressedRLE]
    # keypoints: list[KeyPoints]
    # objects: list[Entity]


class DefaultVideoDatasetItem(DatasetItem):
    """Default Video DatasetItem Schema."""

    image: list[SequenceFrame]
    tracks: list[Track]
    tracklets: list[Tracklet]
    bboxes: list[BBox]
    keypoints: list[KeyPoints]


class DefaultImageDatasetItem(DatasetItem):
    """Default Image DatasetItem Schema."""

    image: Image
    objects: list[Entity]
    bboxes: list[BBox]
    masks: list[CompressedRLE]
    keypoints: list[KeyPoints]
