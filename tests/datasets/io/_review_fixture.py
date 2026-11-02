# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""One record whose annotations carry every review state, for the export-by-review-status tests.

Shared by the JSONL, COCO and CLI tests so all three check the same rows. Each entity is named
after the case it covers; the comments say what a selection of ``{accepted}`` must do with it. A
model's row is pending or accepted: a rejected one is deleted, so no row says so.
"""

from pathlib import Path

import numpy as np
import PIL.Image

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, CompressedRLE, Entity, EntityDynamicState, Image, Record, Relation
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL


REVIEW_DATASET_NAME = "review_ds"
RECORD_ID = "rec"
IMAGE_ID = "img"

MODEL_NAME = "detector"
MODEL_CONFIDENCE = 0.9

# Entities that must survive a {accepted} selection, and those that must not.
KEPT_ENTITIES = {
    "e_human",  # a person's box: never filtered
    "e_truth",  # ground truth: not a model's, never filtered
    "e_accepted",  # its box accepted, as it came or with a person's edit: the two read the same
    "e_mixed",  # its pending box goes, its accepted mask keeps it
    "e_bare",  # never had an annotation: the filter did not empty it
    "e_parent",  # its only box is pending, but a kept child names it as parent_id
    "e_grandparent",  # the same, one level up: kept because e_parent is
    "e_child",
    "e_related",  # its only box is pending, but a kept relation points at that box
    "e_pending",  # its only box is pending, but a model's pending relation points at that box (see below)
}
DROPPED_ENTITIES = {
    "e_pending_only",  # its only box is pending, and nothing else keeps it
    "e_lone_parent",  # parent of e_pending_only only: a dropped child protects nothing
    "e_reimported",  # a model row without a status (re-imported) counts as pending
}

KEPT_ANNOTATIONS = {"b_human", "b_truth", "b_accepted", "m_mixed_accepted", "b_child"}
DROPPED_ANNOTATIONS = {
    "b_pending",
    "b_pending_only",
    "b_reimported",
    "b_mixed_pending",
    "b_parent",
    "b_grandparent",
    "b_lone_parent",
    "b_related",
}

# No person can review a relation yet (`pixano.schemas.is_reviewable_annotation`): a model's
# relation is kept whatever its status, as nobody could have accepted it.
KEPT_RELATIONS = {"r_human", "r_model_pending"}

KEPT_STATES = {"s_mixed"}
DROPPED_STATES = {"s_pending_only"}


class ReviewEntity(Entity):
    """An entity with a class, so the COCO export has categories."""

    category: str = ""


def _box(box_id: str, entity_id: str, source_type: str, review_status: str = "") -> BBox:
    is_model = source_type == "model"
    return BBox(
        id=box_id,
        record_id=RECORD_ID,
        view_id=IMAGE_ID,
        entity_id=entity_id,
        coords=[0.1, 0.2, 0.3, 0.4],
        format="xywh",
        is_normalized=True,
        confidence=MODEL_CONFIDENCE if is_model else -1.0,
        source_type=source_type,
        source_name=MODEL_NAME if is_model else "",
        review_status=review_status,
    )


def build_review_dataset(path: Path) -> Dataset:
    """Create the review fixture dataset at ``path`` (an embedded image, every review state)."""
    image_bytes = Path(IMAGE_JPG_ASSET_URL).read_bytes()
    with PIL.Image.open(IMAGE_JPG_ASSET_URL) as picture:
        width, height = picture.size

    dataset = Dataset.create(
        path,
        DatasetInfo(
            name=REVIEW_DATASET_NAME,
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=ReviewEntity,
            entity_dynamic_state=EntityDynamicState,
            bbox=BBox,
            mask=CompressedRLE,
            relation=Relation,
            views={"image": Image},
        ),
    )

    mask_pixels = np.zeros((height, width), dtype=np.uint8)
    mask_pixels[: height // 2, : width // 2] = 1

    entities = [
        ReviewEntity(id="e_human", record_id=RECORD_ID, category="person"),
        ReviewEntity(id="e_truth", record_id=RECORD_ID, category="person"),
        ReviewEntity(id="e_pending", record_id=RECORD_ID, category="car"),
        ReviewEntity(id="e_accepted", record_id=RECORD_ID, category="car"),
        ReviewEntity(id="e_pending_only", record_id=RECORD_ID, parent_id="e_lone_parent", category="car"),
        ReviewEntity(id="e_lone_parent", record_id=RECORD_ID, category="group"),
        ReviewEntity(id="e_reimported", record_id=RECORD_ID, category="car"),
        ReviewEntity(id="e_mixed", record_id=RECORD_ID, category="car"),
        ReviewEntity(id="e_bare", record_id=RECORD_ID, category="tree"),
        ReviewEntity(id="e_grandparent", record_id=RECORD_ID, category="group"),
        ReviewEntity(id="e_parent", record_id=RECORD_ID, parent_id="e_grandparent", category="group"),
        ReviewEntity(id="e_child", record_id=RECORD_ID, parent_id="e_parent", category="person"),
        ReviewEntity(id="e_related", record_id=RECORD_ID, category="car"),
    ]
    boxes = [
        _box("b_human", "e_human", "human"),
        _box("b_truth", "e_truth", "ground_truth"),
        _box("b_pending", "e_pending", "model", "pending"),
        _box("b_accepted", "e_accepted", "model", "accepted"),
        _box("b_pending_only", "e_pending_only", "model", "pending"),
        _box("b_lone_parent", "e_lone_parent", "model", "pending"),
        _box("b_reimported", "e_reimported", "model"),
        _box("b_mixed_pending", "e_mixed", "model", "pending"),
        _box("b_parent", "e_parent", "model", "pending"),
        _box("b_grandparent", "e_grandparent", "model", "pending"),
        _box("b_child", "e_child", "human"),
        _box("b_related", "e_related", "model", "pending"),
    ]
    masks = [
        CompressedRLE.from_mask(
            mask_pixels,
            id="m_mixed_accepted",
            record_id=RECORD_ID,
            view_id=IMAGE_ID,
            entity_id="e_mixed",
            source_type="model",
            source_name=MODEL_NAME,
            review_status="accepted",
        )
    ]
    # Relations point at annotations (`utils/integrity.py` checks subject_id/object_id against
    # the annotation tables).
    relations = [
        Relation(
            id="r_human",
            record_id=RECORD_ID,
            view_id=IMAGE_ID,
            predicate="next_to",
            subject_id="b_human",
            object_id="b_related",
            source_type="human",
        ),
        Relation(
            id="r_model_pending",
            record_id=RECORD_ID,
            view_id=IMAGE_ID,
            predicate="next_to",
            subject_id="b_human",
            object_id="b_pending",
            source_type="model",
            source_name=MODEL_NAME,
            review_status="pending",
        ),
    ]
    states = [
        EntityDynamicState(id="s_pending_only", record_id=RECORD_ID, entity_id="e_pending_only", view_id=IMAGE_ID),
        EntityDynamicState(id="s_mixed", record_id=RECORD_ID, entity_id="e_mixed", view_id=IMAGE_ID),
    ]

    dataset.add_records(
        {
            "records": [Record(id=RECORD_ID, split="train")],
            "images": [
                Image(
                    id=IMAGE_ID,
                    record_id=RECORD_ID,
                    logical_name="image",
                    raw_bytes=image_bytes,
                    width=width,
                    height=height,
                    format="JPEG",
                )
            ],
            "entities": entities,
            "entity_dynamic_states": states,
            "bboxes": boxes,
            "masks": masks,
            "relations": relations,
        }
    )
    return dataset
