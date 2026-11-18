# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review status a model's annotation carries, how a stored status reads, which fields hold
the model's score, and which kinds and views a person can review."""

import typing

import pytest

from pixano import schemas
from pixano.schemas import (
    NOT_REVIEWED_STATUSES,
    PDF,
    BBox,
    BBox3D,
    CalibratedImage,
    CalibratedPointCloud,
    Classification,
    CompressedRLE,
    Entity,
    Image,
    KeyPoints,
    KeyPoints3D,
    MultiPath,
    PointCloud,
    PointCloudFrame,
    Relation,
    ReviewStatus,
    SequenceFrame,
    Text,
    TextSpan,
    Tracklet,
    Video,
    View,
    is_entity_annotation,
    is_reviewable_annotation,
    is_reviewable_view,
    model_score_alignment,
    model_score_fields,
    review_status_of,
    stored_statuses,
)


# What a model's score is called on the schemas that carry one. A field whose name holds one of
# these words, on an entity annotation, must be declared in MODEL_SCORE_FIELDS.
SCORE_WORDS = ("confidence", "score")


def _annotation_schemas() -> list[type]:
    return [value for value in vars(schemas).values() if isinstance(value, type) and is_entity_annotation(value)]


def _is_list_field(schema: type, name: str) -> bool:
    return typing.get_origin(schema.model_fields[name].annotation) is list


def _box(**fields) -> BBox:
    return BBox(id="b1", coords=[0, 0, 1, 1], format="xyxy", is_normalized=True, **fields)


class TestNotReviewed:
    def test_a_model_row_without_a_status_reads_as_pending(self):
        """Re-imported from JSONL, whose grammar does not carry the status: nobody reviewed it."""
        assert review_status_of("") is ReviewStatus.PENDING
        assert review_status_of("pending") is ReviewStatus.PENDING

    def test_a_decision_reads_as_itself(self):
        assert review_status_of("accepted") is ReviewStatus.ACCEPTED

    @pytest.mark.parametrize("stored", ["approved", "corrected", "rejected"])
    def test_a_value_that_is_no_status_is_refused(self, stored: str):
        """A reject deletes the row and a saved edit accepts it: no status says either."""
        with pytest.raises(ValueError):
            review_status_of(stored)

    def test_a_filter_on_pending_finds_the_rows_stored_without_a_status(self):
        assert set(stored_statuses(ReviewStatus.PENDING)) == set(NOT_REVIEWED_STATUSES) == {"pending", ""}
        assert stored_statuses(ReviewStatus.ACCEPTED) == ("accepted",)


class TestReviewStatus:
    def test_a_model_row_is_pending_or_accepted(self):
        assert [status.value for status in ReviewStatus] == ["pending", "accepted"]

    def test_a_row_takes_a_status_as_its_value(self):
        assert _box(source_type="model", review_status=ReviewStatus.ACCEPTED).review_status == "accepted"

    def test_a_human_row_carries_no_status(self):
        assert _box(source_type="human").review_status == ""

    @pytest.mark.parametrize("status", ["approved", "corrected", "rejected"])
    def test_a_row_cannot_hold_a_value_that_is_no_status(self, status: str):
        """A reject deletes the row and a saved edit accepts it: no status says either. Wherever a
        row is read through its schema, a value no review gives is refused rather than read as
        some status."""
        with pytest.raises(ValueError, match=status):
            _box(source_type="model", review_status=status)


class TestModelScore:
    @pytest.mark.parametrize(
        "schema, fields",
        [(BBox, ("confidence",)), (BBox3D, ("confidence",)), (Classification, ("confidences",))],
    )
    def test_each_schema_declares_its_own(self, schema: type, fields: tuple[str, ...]):
        assert model_score_fields(schema) == fields

    def test_a_subclass_keeps_its_parent_declaration(self):
        class LabelledBox(BBox):
            label: str = ""

        assert model_score_fields(LabelledBox) == ("confidence",)

    @pytest.mark.parametrize("schema", [CompressedRLE, KeyPoints, KeyPoints3D, Tracklet, Entity])
    def test_a_schema_without_a_score_declares_none(self, schema: type):
        assert model_score_fields(schema) == ()

    def test_no_score_field_is_left_undeclared(self):
        """A score left out would be erased by a person's edit, and taken for an edit."""
        annotation_schemas = _annotation_schemas()
        undeclared = {
            (schema.__name__, name)
            for schema in annotation_schemas
            for name in schema.model_fields
            if any(word in name for word in SCORE_WORDS) and name not in model_score_fields(schema)
        }

        assert annotation_schemas
        assert undeclared == set()


class TestModelScoreAlignment:
    def test_a_classification_scores_its_labels(self):
        assert model_score_alignment(Classification) == {"confidences": "labels"}

    @pytest.mark.parametrize("schema", [BBox, BBox3D, CompressedRLE, Tracklet, Entity])
    def test_a_schema_without_a_list_of_scores_aligns_none(self, schema: type):
        assert model_score_alignment(schema) == {}

    def test_every_list_of_scores_says_what_it_scores(self):
        """Left unsaid, a person's relabel would keep the model's scores where they stood, scoring
        other labels, or a different number of them: the row would fail validation with a 400."""
        unaligned = {
            (schema.__name__, name)
            for schema in _annotation_schemas()
            for name in model_score_fields(schema)
            if _is_list_field(schema, name) and name not in model_score_alignment(schema)
        }

        assert unaligned == set()

    def test_an_aligned_score_is_a_declared_score_and_scores_a_list(self):
        misdeclared = {
            (schema.__name__, score, scored)
            for schema in _annotation_schemas()
            for score, scored in model_score_alignment(schema).items()
            if score not in model_score_fields(schema)
            or scored not in schema.model_fields
            or not _is_list_field(schema, scored)
        }

        assert misdeclared == set()


class TestReviewableKinds:
    @pytest.mark.parametrize("schema", [BBox, BBox3D, Classification, CompressedRLE, KeyPoints, MultiPath])
    def test_a_kind_an_interface_shows_can_be_reviewed(self, schema: type):
        assert is_reviewable_annotation(schema)

    @pytest.mark.parametrize("schema", [Tracklet, Relation, TextSpan])
    def test_structure_and_kinds_no_interface_shows_cannot(self, schema: type):
        assert is_entity_annotation(schema)
        assert not is_reviewable_annotation(schema)

    def test_what_is_not_an_annotation_cannot(self):
        assert not is_reviewable_annotation(Entity)


class TestReviewableViews:
    """The views the review interface has a widget for: the queue leaves out a row on any other."""

    @pytest.mark.parametrize("schema", [Image, CalibratedImage, PointCloud, CalibratedPointCloud, Text])
    def test_a_view_the_review_interface_shows(self, schema: type):
        assert is_reviewable_view(schema)

    @pytest.mark.parametrize("schema", [SequenceFrame, Video, PointCloudFrame, PDF, View])
    def test_a_video_its_frames_and_views_it_has_no_widget_for(self, schema: type):
        assert not is_reviewable_view(schema)

    def test_a_schema_of_a_dataset_reads_as_the_view_it_derives_from(self):
        class Camera(Image):
            exposure: float = 0.0

        class Clip(SequenceFrame):
            camera: str = ""

        assert is_reviewable_view(Camera)
        assert not is_reviewable_view(Clip)
