# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The statistics job, run as the runner runs it, on a real dataset: what it writes, and what it refuses."""

import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest
from pixano_worker import runner
from pixano_worker.kinds import OWN_FORM_MARKER, StatisticsKind
from pixano_worker.media import MediaResolver
from pydantic import ValidationError, create_model

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record, SequenceFrame
from pixano.statistics import definitions as definitions_module
from pixano.statistics.defaults import DEFAULT_STATISTIC_CHOICES
from pixano.statistics.definitions import (
    AttributeFilter,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
)


DATASET_ID = "shapes"
WIDTH, HEIGHT = 200, 100
VocEntity = create_model("VocEntity", __base__=Entity, category=(str, ""))

BOX_COUNT = define_statistic(
    StatisticChoices(level=StatisticLevel.RECORD, element="bbox", measure=StatisticMeasure.COUNT)
)
DOG_COUNT = define_statistic(
    StatisticChoices(
        level=StatisticLevel.RECORD,
        element="entity",
        measure=StatisticMeasure.COUNT,
        attribute=AttributeFilter(field="category", value="dog"),
    )
)
MEAN_BOX_AREA = define_statistic(
    StatisticChoices(
        level=StatisticLevel.RECORD,
        element="bbox",
        measure=StatisticMeasure.AREA,
        aggregation=StatisticAggregation.MEAN,
    )
)
BOXES_PER_OBJECT = define_statistic(
    StatisticChoices(level=StatisticLevel.ENTITY, element="bbox", measure=StatisticMeasure.COUNT)
)
MASK_COUNT = define_statistic(
    StatisticChoices(level=StatisticLevel.RECORD, element="mask", measure=StatisticMeasure.COUNT)
)
MEAN_MASK_SHARE = define_statistic(
    StatisticChoices(
        level=StatisticLevel.RECORD,
        element="mask",
        measure=StatisticMeasure.IMAGE_RATIO,
        aggregation=StatisticAggregation.MEAN,
    )
)


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A dataset of two images: a dog with two boxes and a cat with one on the first, nothing on the second."""
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay apart.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Shapes", record=Record, entity=VocEntity, bbox=BBox, views={"image": Image}),
    )
    dataset.add_records({"records": [Record(id="r1"), Record(id="r2")]})
    dataset.add_data(
        "images",
        [
            Image(id=f"v{n}", record_id=f"r{n}", logical_name="image", uri=f"{n}.png", width=WIDTH, height=HEIGHT)
            for n in (1, 2)
        ],
        raise_or_warn="none",
    )
    dataset.add_data(
        "entities",
        [VocEntity(id="dog", record_id="r1", category="dog"), VocEntity(id="cat", record_id="r1", category="cat")],
        raise_or_warn="none",
    )
    # 0.5 × 200 by 0.5 × 100, 0.1 × 200 by 0.2 × 100, 0.2 × 200 by 0.5 × 100 pixels.
    boxes = [
        ("b1", "dog", [0.0, 0.0, 0.5, 0.5]),
        ("b2", "dog", [0.5, 0.5, 0.1, 0.2]),
        ("b3", "cat", [0.0, 0.5, 0.2, 0.5]),
    ]
    dataset.add_data(
        "bboxes",
        [
            BBox(
                id=box_id,
                record_id="r1",
                view_id="v1",
                entity_id=entity,
                coords=coords,
                format="xywh",
                is_normalized=True,
            )
            for box_id, entity, coords in boxes
        ],
        raise_or_warn="none",
    )
    return library


def _params(statistics: list[Any], chunk_size: int = 1) -> Any:
    return StatisticsKind().validate_params(
        {"statistics": [statistic.model_dump(mode="json") for statistic in statistics], "chunk_size": chunk_size}
    )


def _run(
    library: Path, statistics: list[Any], job_id: str = "job-1", chunk_size: int = 1, dataset_id: str = DATASET_ID
) -> None:
    """One job as the runner runs it, without the queue: planned and prepared, each chunk processed
    and written, then finalized on the dataset reopened."""
    kind = StatisticsKind()
    params = _params(statistics, chunk_size)
    media = MediaResolver(str(library), str(library))
    chunks = runner._plan_and_prepare(kind, library, dataset_id, media, job_id, params, threading.Event())
    for chunk in chunks:
        result = kind.process(runner._reader_for(library, dataset_id, media), chunk.payload, params)
        kind.write(runner._writer_for(library, dataset_id, kind, job_id, params), result, chunk.payload, params)
    runner._reopen_dataset(library, dataset_id)
    kind.finalize(
        runner._reader_for(library, dataset_id, media),
        runner._writer_for(library, dataset_id, kind, job_id, params),
        params,
    )


def _rows(library: Path, table: str, dataset_id: str = DATASET_ID) -> dict[str, dict[str, Any]]:
    dataset = Dataset.find(dataset_id, library)
    return {row["id"]: row for row in dataset.open_table(table).to_arrow().to_pylist()}


class TestValues:
    def test_per_record(self, library: Path) -> None:
        _run(library, [BOX_COUNT, DOG_COUNT, MEAN_BOX_AREA])

        rows = _rows(library, "record_statistics")
        assert {record: (row["bbox_count"], row["entity_count_category_dog"]) for record, row in rows.items()} == {
            "r1": (3, 1),
            "r2": (0, 0),
        }
        assert rows["r1"]["bbox_area_mean_px"] == pytest.approx((5000 + 400 + 2000) / 3)
        assert rows["r2"]["bbox_area_mean_px"] is None

    def test_per_object(self, library: Path) -> None:
        _run(library, [BOXES_PER_OBJECT])

        rows = _rows(library, "entity_statistics")
        assert {entity: (row["record_id"], row["entity_id"], row["bbox_count"]) for entity, row in rows.items()} == {
            "dog": ("r1", "dog", 2),
            "cat": ("r1", "cat", 1),
        }

    def test_the_dataset_says_what_it_computed(self, library: Path) -> None:
        _run(library, [BOX_COUNT, BOXES_PER_OBJECT], job_id="job-7")

        dataset = Dataset.find(DATASET_ID, library)
        assert [
            (computed.definition.level, computed.definition.name, computed.job_id)
            for computed in dataset.info.statistics
        ] == [
            (StatisticLevel.RECORD, "bbox_count", "job-7"),
            (StatisticLevel.ENTITY, "bbox_count", "job-7"),
        ]
        info = json.loads((library / DATASET_ID / "info.json").read_text())
        assert info["record_statistics"] == {"base": "RecordStatistics", "fields": {}}
        assert info["entity_statistics"] == {"base": "EntityStatistics", "fields": {}}


class TestRerun:
    def test_writes_the_same_values_over_the_same_rows(self, library: Path) -> None:
        _run(library, [BOX_COUNT, BOXES_PER_OBJECT])
        first = (_rows(library, "record_statistics"), _rows(library, "entity_statistics"))

        _run(library, [BOX_COUNT, BOXES_PER_OBJECT], job_id="job-2", chunk_size=2)

        assert (_rows(library, "record_statistics"), _rows(library, "entity_statistics")) == first

    def test_another_statistic_keeps_the_values_of_the_first(self, library: Path) -> None:
        _run(library, [BOX_COUNT])

        _run(library, [DOG_COUNT], job_id="job-2")

        rows = _rows(library, "record_statistics")
        assert {record: (row["bbox_count"], row["entity_count_category_dog"]) for record, row in rows.items()} == {
            "r1": (3, 1),
            "r2": (0, 0),
        }
        dataset = Dataset.find(DATASET_ID, library)
        assert [(computed.definition.name, computed.job_id) for computed in dataset.info.statistics] == [
            ("bbox_count", "job-1"),
            ("entity_count_category_dog", "job-2"),
        ]

    def test_an_object_deleted_between_its_measure_and_the_write_loses_its_row(self, library: Path) -> None:
        _run(library, [BOXES_PER_OBJECT])
        kind, params = StatisticsKind(), _params([BOXES_PER_OBJECT], chunk_size=2)
        media = MediaResolver(str(library), str(library))
        [chunk] = runner._plan_and_prepare(kind, library, DATASET_ID, media, "job-2", params, threading.Event())
        result = kind.process(runner._reader_for(library, DATASET_ID, media), chunk.payload, params)

        dataset = Dataset.find(DATASET_ID, library)
        dataset.delete_data("bboxes", ["b3"])
        dataset.delete_data("entities", ["cat"])
        kind.write(runner._writer_for(library, DATASET_ID, kind, "job-2", params), result, chunk.payload, params)

        assert set(_rows(library, "entity_statistics")) == {"dog"}

    def test_an_object_deleted_since_loses_its_row(self, library: Path) -> None:
        _run(library, [BOXES_PER_OBJECT])
        dataset = Dataset.find(DATASET_ID, library)
        dataset.delete_data("bboxes", ["b3"])
        dataset.delete_data("entities", ["cat"])

        _run(library, [BOXES_PER_OBJECT], job_id="job-2")

        assert set(_rows(library, "entity_statistics")) == {"dog"}


class TestRefused:
    def test_a_statistic_of_what_the_dataset_does_not_hold(self, library: Path) -> None:
        with pytest.raises(ValueError, match="does not hold"):
            _run(library, [BOX_COUNT, MASK_COUNT])

    def test_a_masks_area_by_name_its_geometry_not_read_yet(self, library: Path) -> None:
        with pytest.raises(ValueError, match=f"not measured yet: {MEAN_MASK_SHARE.label}"):
            _run(library, [BOX_COUNT, MEAN_MASK_SHARE])

    def test_a_statistic_whose_measure_changed_since_it_was_composed(self, library: Path, monkeypatch) -> None:
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)

        with pytest.raises(ValueError, match="computed otherwise"):
            _run(library, [BOX_COUNT])

    def test_a_chunk_whose_measure_changed_since_the_job_was_planned(self, library: Path, monkeypatch) -> None:
        """A worker updated between the plan and a chunk would write a new computation in the old column."""
        kind, params = StatisticsKind(), _params([BOX_COUNT])
        media = MediaResolver(str(library), str(library))
        chunks = runner._plan_and_prepare(kind, library, DATASET_ID, media, "job-1", params, threading.Event())
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)

        with pytest.raises(ValueError, match="computed otherwise"):
            kind.process(runner._reader_for(library, DATASET_ID, media), chunks[0].payload, params)

    def test_a_chunk_measuring_a_masks_area_a_worker_measuring_it_planned(self, library: Path) -> None:
        """A worker that measures masks' areas may plan the job; this one writes no value it cannot measure."""
        kind = StatisticsKind()
        media = MediaResolver(str(library), str(library))
        chunks = runner._plan_and_prepare(
            kind, library, DATASET_ID, media, "job-1", _params([BOX_COUNT]), threading.Event()
        )

        with pytest.raises(ValueError, match=f"not measured yet: {MEAN_MASK_SHARE.label}"):
            kind.process(
                runner._reader_for(library, DATASET_ID, media),
                chunks[0].payload,
                _params([BOX_COUNT, MEAN_MASK_SHARE]),
            )

    def test_a_statistic_asked_twice(self) -> None:
        with pytest.raises(ValidationError):
            StatisticsKind().validate_params({"statistics": [BOX_COUNT.model_dump(mode="json")] * 2})

    def test_by_the_generic_form_which_cannot_build_its_parameters(self) -> None:
        assert StatisticsKind().params_schema()[OWN_FORM_MARKER] == "statistics"


class TestTheDefaultStatistics:
    def test_the_parameters_an_import_queues_are_taken_as_they_come(self) -> None:
        """The application queues every default statistic after an import, as JSON (`_fit_statistics`)."""
        defaults = [define_statistic(choices) for choices in DEFAULT_STATISTIC_CHOICES]

        params = StatisticsKind().validate_params({"statistics": [d.model_dump(mode="json") for d in defaults]})

        assert params.statistics == defaults


class TestVideo:
    def test_a_box_on_a_frame_is_measured_against_the_frame(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
        library = tmp_path / "library"
        dataset = Dataset.create(
            library / "clips",
            DatasetInfo(
                id="clips", name="Clips", record=Record, entity=Entity, bbox=BBox, views={"video": SequenceFrame}
            ),
        )
        dataset.add_records({"records": [Record(id="r1")]})
        frame = SequenceFrame(
            id="f0", record_id="r1", logical_name="video", width=WIDTH, height=HEIGHT, timestamp=0.0, frame_index=0
        )
        dataset.add_data("sequence_frames", [frame], raise_or_warn="none")
        dataset.add_data("entities", [Entity(id="car", record_id="r1")], raise_or_warn="none")
        box = BBox(
            id="b1",
            record_id="r1",
            view_id="f0",
            entity_id="car",
            coords=[0.0, 0.0, 0.5, 0.5],
            format="xywh",
            is_normalized=True,
        )
        dataset.add_data("bboxes", [box], raise_or_warn="none")

        _run(library, [MEAN_BOX_AREA], dataset_id="clips")

        assert _rows(library, "record_statistics", "clips")["r1"]["bbox_area_mean_px"] == pytest.approx(
            0.5 * WIDTH * 0.5 * HEIGHT
        )

    def test_a_box_naming_its_frame_is_measured_against_that_frame(self, tmp_path: Path, monkeypatch) -> None:
        """A box of a sequence names the sequence's first view, and its own frame apart."""
        monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
        library = tmp_path / "library"
        info = DatasetInfo(
            id="clips", name="Clips", record=Record, entity=Entity, bbox=BBox, views={"video": SequenceFrame}
        )
        dataset = Dataset.create(library / "clips", info)
        dataset.add_records({"records": [Record(id="r1")]})
        frames = [
            SequenceFrame(
                id=f"f{index}",
                record_id="r1",
                logical_name="video",
                width=WIDTH * (index + 1),
                height=HEIGHT,
                timestamp=float(index),
                frame_index=index,
            )
            for index in range(2)
        ]
        dataset.add_data("sequence_frames", frames, raise_or_warn="none")
        dataset.add_data("entities", [Entity(id="car", record_id="r1")], raise_or_warn="none")
        box = BBox(
            id="b1",
            record_id="r1",
            view_id="f0",
            frame_id="f1",
            entity_id="car",
            coords=[0.0, 0.0, 0.5, 0.5],
            format="xywh",
            is_normalized=True,
        )
        dataset.add_data("bboxes", [box], raise_or_warn="none")

        _run(library, [MEAN_BOX_AREA], dataset_id="clips")

        assert _rows(library, "record_statistics", "clips")["r1"]["bbox_area_mean_px"] == pytest.approx(
            0.5 * 2 * WIDTH * 0.5 * HEIGHT
        )
