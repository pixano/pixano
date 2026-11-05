# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A statistic composed from fixed choices: what it may be made of, and the column it names."""

import pytest
from pydantic import ValidationError

from pixano.schemas import ReviewStatus
from pixano.statistics import definitions as definitions_module
from pixano.statistics.definitions import (
    MAX_ATTRIBUTE_VALUE_LENGTH,
    MAX_COLUMN_NAME_LENGTH,
    MAX_LABEL_LENGTH,
    AnnotationOrigin,
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticDefinition,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
    is_reviewable_element,
)


def _choices(**changes) -> StatisticChoices:
    fields = {"level": StatisticLevel.RECORD, "element": "bbox", "measure": StatisticMeasure.COUNT} | changes
    return StatisticChoices(**fields)


class TestColumnName:
    """The column a statistic's values go to says what they are, with their unit."""

    def test_a_count(self) -> None:
        assert _choices().column_name() == "bbox_count"

    def test_an_area_in_pixels(self) -> None:
        choices = _choices(measure=StatisticMeasure.AREA, aggregation=StatisticAggregation.MEAN)
        assert choices.column_name() == "bbox_area_mean_px"

    def test_a_share_of_the_image(self) -> None:
        choices = _choices(element="mask", measure=StatisticMeasure.IMAGE_RATIO, aggregation=StatisticAggregation.MAX)
        assert choices.column_name() == "mask_to_image_ratio_max"

    def test_a_filter_adds_what_it_keeps(self) -> None:
        choices = _choices(
            attribute=AttributeFilter(field="category", value="Traffic Light"),
            origin=AnnotationOrigin.MODEL,
            review_status=ReviewStatus.PENDING,
        )
        assert choices.column_name() == "bbox_count_category_traffic_light_by_model_pending"

    def test_annotations_not_made_by_a_model(self) -> None:
        assert _choices(origin=AnnotationOrigin.NOT_MODEL).column_name() == "bbox_count_not_by_model"

    def test_an_accented_value_keeps_its_letters(self) -> None:
        assert _choices(attribute=AttributeFilter(field="catégorie", value="Vélo")).column_name() == (
            "bbox_count_categorie_velo"
        )

    @pytest.mark.parametrize(
        "value,part", [("Straße", "strasse"), ("Øre", "ore"), ("Æble", "aeble"), ("Łódź", "lodz")]
    )
    def test_letters_a_decomposition_keeps_are_written_out(self, value: str, part: str) -> None:
        assert _choices(attribute=AttributeFilter(field="city", value=value)).column_name() == (
            f"bbox_count_city_{part}"
        )

    def test_a_value_of_symbols_alone_keeps_a_name_of_its_own(self) -> None:
        first = _choices(attribute=AttributeFilter(field="category", value="???")).column_name()
        second = _choices(attribute=AttributeFilter(field="category", value="!!!")).column_name()

        assert first.startswith("bbox_count_category_value_")
        assert first != second

    def test_a_long_name_is_cut_and_stays_apart(self) -> None:
        long_value = "a very long category name " * 4
        first = _choices(attribute=AttributeFilter(field="category", value=long_value + "one")).column_name()
        second = _choices(attribute=AttributeFilter(field="category", value=long_value + "two")).column_name()

        assert len(first) <= MAX_COLUMN_NAME_LENGTH
        assert len(second) <= MAX_COLUMN_NAME_LENGTH
        assert first != second

    def test_a_measure_past_its_first_version_has_a_column_of_its_own(self, monkeypatch) -> None:
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)
        assert _choices().column_name() == "bbox_count_v2"


class TestMeaningfulChoices:
    """A combination that measures nothing meaningful is refused."""

    @pytest.mark.parametrize(
        "changes",
        [
            {"element": "unicorn"},
            {"level": StatisticLevel.ENTITY, "element": "entity"},
            {"element": "keypoint", "measure": StatisticMeasure.AREA, "aggregation": StatisticAggregation.MEAN},
            {"aggregation": StatisticAggregation.MEAN},
            {"measure": StatisticMeasure.AREA},
            {"element": "entity", "origin": AnnotationOrigin.MODEL},
            {"element": "entity", "review_status": ReviewStatus.ACCEPTED},
            {"origin": AnnotationOrigin.NOT_MODEL, "review_status": ReviewStatus.PENDING},
            {"element": "tracklet", "review_status": ReviewStatus.ACCEPTED},
            {"element": "text_span", "review_status": ReviewStatus.PENDING},
        ],
        ids=[
            "an unknown element",
            "objects counted per object",
            "the area of keypoints",
            "an aggregated count",
            "an area without aggregation",
            "the origin of objects",
            "the review status of objects",
            "a review status of annotations no model made",
            "a review status of tracks, which no interface reviews",
            "a review status of text spans, which no interface reviews",
        ],
    )
    def test_refused(self, changes) -> None:
        with pytest.raises(ValidationError):
            _choices(**changes)

    def test_a_review_status_alone_is_a_models_annotations(self) -> None:
        """The same statistic with or without the origin it implies: the same name."""
        alone = _choices(review_status=ReviewStatus.PENDING)

        assert alone.origin is AnnotationOrigin.MODEL
        assert alone == _choices(origin=AnnotationOrigin.MODEL, review_status=ReviewStatus.PENDING)

    def test_an_attribute_value_has_a_bound(self) -> None:
        with pytest.raises(ValidationError):
            AttributeFilter(field="category", value="x" * (MAX_ATTRIBUTE_VALUE_LENGTH + 1))

    def test_the_objects_of_a_record_are_counted(self) -> None:
        assert _choices(element="entity").column_name() == "entity_count"

    def test_the_boxes_of_an_object_are_counted(self) -> None:
        assert _choices(level=StatisticLevel.ENTITY).column_name() == "bbox_count"


class TestDefinition:
    """What the library keeps of a statistic: its column, a label, a unit, a type, a version."""

    def test_a_count_is_whole_and_has_no_unit(self) -> None:
        definition = define_statistic(_choices())

        assert (definition.name, definition.value_type, definition.unit, definition.version) == (
            "bbox_count",
            "int",
            "",
            1,
        )

    def test_an_area_is_decimal_in_pixels(self) -> None:
        definition = define_statistic(_choices(measure=StatisticMeasure.AREA, aggregation=StatisticAggregation.SUM))

        assert (definition.value_type, definition.unit) == ("float", "px²")

    def test_a_label_is_made_from_the_choices_when_none_is_given(self) -> None:
        definition = define_statistic(
            _choices(
                measure=StatisticMeasure.AREA,
                aggregation=StatisticAggregation.MEAN,
                attribute=AttributeFilter(field="category", value="dog"),
                origin=AnnotationOrigin.MODEL,
            ),
            label="   ",
        )

        assert definition.label == "Mean area of the boxes, category dog, made by a model"

    def test_a_label_made_from_a_long_value_is_cut(self) -> None:
        long_value = "x" * MAX_ATTRIBUTE_VALUE_LENGTH
        definition = define_statistic(_choices(attribute=AttributeFilter(field="category", value=long_value)))

        assert len(definition.label) == MAX_LABEL_LENGTH
        assert definition.label.endswith("…")

    def test_a_label_given_is_kept(self) -> None:
        definition = define_statistic(_choices(), label="  Boxes  ", description=" mine ")

        assert (definition.label, definition.description) == ("Boxes", "mine")

    def test_a_statistic_composed_before_its_measure_changed_is_no_longer_current(self, monkeypatch) -> None:
        definition = define_statistic(_choices())
        assert definition.is_current

        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)

        assert not definition.is_current
        assert define_statistic(_choices()).label == "Number of boxes, version 2"

    @pytest.mark.parametrize(
        "changes",
        [{"level": "entity"}, {"value_type": "float"}, {"unit": "px²"}],
        ids=["another table", "another type", "another unit"],
    )
    def test_one_that_says_otherwise_than_its_choices_is_refused(self, changes: dict) -> None:
        """A definition can come back from a job's parameters too, which anybody can send."""
        with pytest.raises(ValidationError, match="its choices|its measure"):
            StatisticDefinition.model_validate(define_statistic(_choices()).model_dump() | changes)

    @pytest.mark.parametrize("name", ["record.bbox_count", "_rowid", "Bbox_count", "", "x" * 64])
    def test_a_name_is_a_column_name_whoever_wrote_it(self, name: str) -> None:
        """A definition can come back from a job's parameters too, which anybody can send."""
        with pytest.raises(ValidationError):
            StatisticDefinition.model_validate(define_statistic(_choices()).model_dump() | {"name": name})


@pytest.mark.parametrize(
    "element,reviewable",
    [("bbox", True), ("mask", True), ("tracklet", False), ("text_span", False), ("entity", False), ("nope", False)],
)
def test_the_elements_whose_annotations_have_a_review_status(element: str, reviewable: bool) -> None:
    assert is_reviewable_element(element) is reviewable
