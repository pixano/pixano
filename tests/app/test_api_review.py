# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review of a model's annotations through the API, beyond one box's update.

`GET /datasets/{id}/review/next` finds the next record holding a model's annotations at a status.
It looks for model annotations of any kind a person can review, here boxes and masks, and must
leave the dataset's tables as they are. The rules of an update that reach past the row it names are
here too: a person's edit of an entity accepts the model's pending annotations naming it, and each
kind's own score stays the model's through a person's edit, following what it scores.
"""

import json
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, Classification, CompressedRLE, Entity, Image, Record, Relation, TextSpan, Tracklet


DATASET_ID = "review"
BASE = f"/datasets/{DATASET_ID}"
NEXT = f"{BASE}/review/next"

MODEL = {"source_type": "model", "source_name": "detection", "source_metadata": '{"model": "yolo"}'}
HUMAN = {"source_type": "ground_truth", "source_name": "Ground Truth"}
MASK_SHAPE = (4, 4)

# What each record holds. r2 has a person's annotations only, and r6 holds nothing.
PENDING_RECORDS = ["r1", "r3", "r5"]
ACCEPTED_RECORDS = ["r3", "r4"]
RECORD_IDS = ["r1", "r2", "r3", "r4", "r5", "r6"]


def _box(box_id: str, record_id: str, status: str, source: dict[str, str]) -> BBox:
    return BBox(
        id=box_id,
        record_id=record_id,
        entity_id=f"entity_{box_id}",
        view_id="image",
        coords=[0.1, 0.1, 0.2, 0.2],
        format="xywh",
        is_normalized=True,
        review_status=status,
        **source,
    )


def _mask(mask_id: str, record_id: str, status: str, source: dict[str, str]) -> CompressedRLE:
    return CompressedRLE.from_mask(
        np.ones(MASK_SHAPE, dtype=np.uint8),
        id=mask_id,
        record_id=record_id,
        entity_id=f"entity_{mask_id}",
        view_id="image",
        review_status=status,
        **source,
    )


def _create(path: Path, info: DatasetInfo, boxes: list[BBox], masks: list[CompressedRLE]) -> Dataset:
    dataset = Dataset.create(path, info)
    dataset.add_records({"records": [Record(id=record_id) for record_id in RECORD_IDS]})
    annotations = [*boxes, *masks]
    entities = [Entity(id=row.entity_id, record_id=row.record_id) for row in annotations]
    dataset.add_data("entities", entities, raise_or_warn="none")
    if boxes:
        dataset.add_data("bboxes", boxes, raise_or_warn="none")
    if masks:
        dataset.add_data("masks", masks, raise_or_warn="none")
    return dataset


def _client(dataset: Dataset) -> TestClient:
    models_dir = Path(tempfile.mkdtemp()) / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(dataset.path.parent), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


@pytest.fixture
def dataset() -> Dataset:
    """Boxes and masks at every status, the way the worker writes a model's output."""
    boxes = [
        _box("box_r1_pending", "r1", "pending", MODEL),
        _box("box_r2_human", "r2", "", HUMAN),
        _box("box_r3_pending", "r3", "pending", MODEL),
        _box("box_r3_accepted", "r3", "accepted", MODEL),
        _box("box_r4_accepted", "r4", "accepted", MODEL),
    ]
    masks = [
        _mask("mask_r2_human", "r2", "", HUMAN),
        _mask("mask_r5_pending", "r5", "pending", MODEL),
    ]
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        record=Record,
        entity=Entity,
        bbox=BBox,
        mask=CompressedRLE,
        views={"image": Image},
    )
    return _create(Path(tempfile.mkdtemp()) / DATASET_ID, info, boxes, masks)


@pytest.fixture
def client(dataset: Dataset) -> TestClient:
    return _client(dataset)


def _next(client: TestClient, **params) -> dict:
    resp = client.get(NEXT, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestNextRecordToReview:
    def test_starts_at_the_first_record_holding_a_pending_annotation(self, client: TestClient):
        assert _next(client) == {"record_id": "r1", "remaining": len(PENDING_RECORDS)}

    def test_goes_through_the_records_in_id_order_and_wraps_round(self, client: TestClient):
        visited = [_next(client, after=record_id)["record_id"] for record_id in PENDING_RECORDS]

        assert visited == ["r3", "r5", "r1"]

    def test_finds_a_record_whose_only_pending_annotation_is_a_mask(self, client: TestClient):
        assert _next(client, after="r4")["record_id"] == "r5"

    def test_never_returns_a_record_holding_only_a_person_annotations(self, client: TestClient):
        returned = {_next(client, after=record_id)["record_id"] for record_id in RECORD_IDS}

        assert returned == set(PENDING_RECORDS)

    def test_a_record_left_without_pending_annotations_drops_out(self, client: TestClient):
        """A decision saved through the API takes the record out of the queue."""
        resp = client.put(f"{BASE}/bboxes/box_r1_pending", json={"review_status": "accepted"})
        assert resp.status_code == 200, resp.text

        assert _next(client) == {"record_id": "r3", "remaining": len(PENDING_RECORDS) - 1}

    def test_answers_null_when_nothing_is_left(self, client: TestClient):
        """Accepted, or rejected: a reject is the row's delete, as the interface sends it."""
        for resource, row_id in [("bboxes", "box_r1_pending"), ("masks", "mask_r5_pending")]:
            resp = client.put(f"{BASE}/{resource}/{row_id}", json={"review_status": "accepted"})
            assert resp.status_code == 200, resp.text
        resp = client.delete(f"{BASE}/bboxes/box_r3_pending", params={"prune_orphan_entity": True})
        assert resp.status_code == 204, resp.text

        assert _next(client, after="r3") == {"record_id": None, "remaining": 0}

    def test_follows_the_status_asked_for(self, client: TestClient):
        assert _next(client, status="accepted") == {"record_id": "r3", "remaining": len(ACCEPTED_RECORDS)}
        assert _next(client, status="accepted", after="r4")["record_id"] == "r3"

    def test_a_model_row_without_a_status_counts_as_pending(self, dataset: Dataset, client: TestClient):
        """A re-imported model row has no status, since the JSONL does not carry it yet. It was
        never reviewed, as the export by status also reads it."""
        # Written before the API's first request. Once open, the API's dataset does not see what
        # another instance writes until it writes itself or reopens (known defect, spec §18).
        dataset.add_data("entities", [Entity(id="entity_box_r6", record_id="r6")], raise_or_warn="none")
        dataset.add_data("bboxes", [_box("box_r6", "r6", "", MODEL)], raise_or_warn="none")

        assert _next(client, after="r5") == {"record_id": "r6", "remaining": len(PENDING_RECORDS) + 1}

    @pytest.mark.parametrize("status", ["approved", "", "PENDING", "corrected", "rejected"])
    def test_refuses_a_status_that_does_not_exist(self, client: TestClient, status: str):
        assert client.get(NEXT, params={"status": status}).status_code == 422

    def test_creates_no_table_on_a_dataset_without_masks(self):
        """The scan reads the tables the dataset has. Going through `BaseService.resolve_table`
        would create every annotation table it asks about."""
        info = DatasetInfo(
            id=DATASET_ID, name=DATASET_ID, record=Record, entity=Entity, bbox=BBox, views={"image": Image}
        )
        path = Path(tempfile.mkdtemp()) / DATASET_ID
        dataset = _create(path, info, [_box("box_r1_pending", "r1", "pending", MODEL)], [])
        tables_before = set(dataset.info.tables)
        assert "masks" not in tables_before

        assert _next(_client(dataset)) == {"record_id": "r1", "remaining": 1}

        assert set(Dataset(path).info.tables) == tables_before
        assert not (path / Dataset._DB_PATH / "masks.lance").exists()

    def test_a_kind_no_person_can_review_does_not_hold_the_queue(self):
        """No interface shows a tracklet, a relation or a text span for review. A model's row of
        one of them would keep its record in the queue for good: a reviewer moving to the next
        record would cycle over records showing nothing to review, and `remaining` would never
        reach 0."""
        info = DatasetInfo(
            id=DATASET_ID,
            name=DATASET_ID,
            record=Record,
            entity=Entity,
            bbox=BBox,
            tracklet=Tracklet,
            relation=Relation,
            text_span=TextSpan,
            views={"image": Image},
        )
        dataset = _create(Path(tempfile.mkdtemp()) / DATASET_ID, info, [_box("box_r4", "r4", "pending", MODEL)], [])
        unreviewable = {
            "tracklets": Tracklet(id="tracklet_r1", record_id="r1", entity_id="entity_r1", **MODEL),
            "relations": Relation(id="relation_r2", record_id="r2", predicate="next_to", **MODEL),
            "text_spans": TextSpan(
                id="span_r3",
                record_id="r3",
                entity_id="entity_r3",
                mention="a",
                spans_start=[0],
                spans_end=[1],
                **MODEL,
            ),
        }
        for table_name, row in unreviewable.items():
            dataset.add_data(table_name, [row], raise_or_warn="none")

        assert _next(_client(dataset)) == {"record_id": "r4", "remaining": 1}


# A person's edit of what an entity says, and each kind's score
# =============================================================

BOX_COORDS = [0.1, 0.1, 0.2, 0.2]
MODEL_SCORES = [0.87]
# What the annotation interface (ui/apps/web) sends with every edit: its own provenance, and a
# score of 1 (classificationPayloadBuilder.ts, `geometryForEntity`).
WEB_SOURCE = {"source_type": "other", "source_name": "Pixano", "source_metadata": "{}"}
WEB_SCORES = [1.0]


class LabelledEntity(Entity):
    """An object with its class, where a detection writes the class it found."""

    category: str = ""


def _labelled_dataset() -> Dataset:
    """Objects found by a model, each with a box at one status, and the car's classification.

    The car also holds a person's box, and the bus's box is already accepted.
    """
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        record=Record,
        entity=LabelledEntity,
        bbox=BBox,
        classification=Classification,
        views={"image": Image},
    )
    dataset = Dataset.create(Path(tempfile.mkdtemp()) / DATASET_ID, info)
    dataset.add_records({"records": [Record(id=record_id) for record_id in RECORD_IDS]})
    objects = {"car": "pending", "bus": "accepted", "cat": "pending"}
    entities = [
        LabelledEntity(id=f"e_{name}", record_id="r1" if name != "cat" else "r2", category=name) for name in objects
    ]
    boxes = [
        BBox(
            id=f"box_{name}",
            record_id=entity.record_id,
            entity_id=entity.id,
            view_id="image",
            coords=BOX_COORDS,
            format="xywh",
            is_normalized=True,
            confidence=MODEL_SCORES[0],
            review_status=status,
            **MODEL,
        )
        for (name, status), entity in zip(objects.items(), entities, strict=True)
    ]
    boxes.append(_box("box_car_person", "r1", "", HUMAN).model_copy(update={"entity_id": "e_car"}))
    classification = Classification(
        id="cls_car",
        record_id="r1",
        entity_id="e_car",
        view_id="image",
        labels=["car"],
        confidences=MODEL_SCORES,
        review_status="pending",
        **MODEL,
    )
    dataset.add_data("entities", entities, raise_or_warn="none")
    dataset.add_data("bboxes", boxes, raise_or_warn="none")
    dataset.add_data("classifications", [classification], raise_or_warn="none")
    return dataset


@pytest.fixture
def labelled_client() -> TestClient:
    return _client(_labelled_dataset())


def _get_row(dataset: Dataset, table_name: str, row_id: str) -> Any:
    return dataset.get_data(table_name, ids=[row_id])[0]


def _get(client: TestClient, resource: str, row_id: str) -> dict:
    resp = client.get(f"{BASE}/{resource}/{row_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _legacy_entity_edit(client: TestClient, entity_id: str, **changes) -> dict:
    """What the legacy interface's object inspector sends: the entity it read, changed
    (entityCardOps.ts, `saveInputChange`)."""
    read = _get(client, "entities", entity_id)
    body = {key: value for key, value in read.items() if key not in ("created_at", "updated_at")}
    resp = client.put(f"{BASE}/entities/{entity_id}", json={**body, **changes})
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAnEntityEditAccepts:
    """A detection's class lives in its entity. A person who fixes it there saves an edit of what
    the model's annotations naming that entity say, which accepts them: left pending, the next run
    would write the model's class back, and the queue and the export by status would read them as
    never reviewed."""

    def test_relabelling_an_object_accepts_every_pending_model_annotation_naming_it(self, labelled_client: TestClient):
        box_before = _get(labelled_client, "bboxes", "box_car")

        _legacy_entity_edit(labelled_client, "e_car", category="truck")

        box = _get(labelled_client, "bboxes", "box_car")
        assert box["review_status"] == "accepted"
        excluded = ("review_status", "created_at", "updated_at")
        assert {k: v for k, v in box.items() if k not in excluded} == {
            k: v for k, v in box_before.items() if k not in excluded
        }
        assert _get(labelled_client, "classifications", "cls_car")["review_status"] == "accepted"

    def test_a_person_annotation_and_another_object_are_left_alone(self, labelled_client: TestClient):
        _legacy_entity_edit(labelled_client, "e_car", category="truck")

        person_box = _get(labelled_client, "bboxes", "box_car_person")
        assert (person_box["review_status"], person_box["source_type"]) == ("", HUMAN["source_type"])
        assert _get(labelled_client, "bboxes", "box_cat")["review_status"] == "pending"

    def test_an_accepted_annotation_stays_accepted(self):
        """Already a person's work: the edit does not even rewrite it."""
        dataset = _labelled_dataset()
        client = _client(dataset)
        box_before = _get(client, "bboxes", "box_bus")
        boxes_version = Dataset(dataset.path).open_table("bboxes").version

        _legacy_entity_edit(client, "e_bus", category="truck")

        assert _get(client, "bboxes", "box_bus") == box_before
        assert Dataset(dataset.path).open_table("bboxes").version == boxes_version

    def test_a_model_annotation_without_a_status_is_accepted_too(self):
        """A re-imported model row has no status, since the JSONL does not carry it yet, and reads as
        pending (`pixano.schemas.NOT_REVIEWED_STATUSES`). The edit looks for the rows to accept by
        their stored status: it must name the empty one, or the row stays without a status and the
        queue and the export by status read it as never reviewed."""
        dataset = _labelled_dataset()
        without_status = _get_row(dataset, "bboxes", "box_car").model_copy(
            update={"id": "box_car_without_status", "review_status": ""}
        )
        dataset.add_data("bboxes", [without_status], raise_or_warn="none")
        client = _client(dataset)

        _legacy_entity_edit(client, "e_car", category="truck")

        assert _get(client, "bboxes", "box_car_without_status")["review_status"] == "accepted"

    def test_the_record_leaves_the_queue(self, labelled_client: TestClient):
        assert _next(labelled_client) == {"record_id": "r1", "remaining": 2}

        _legacy_entity_edit(labelled_client, "e_car", category="truck")

        assert _next(labelled_client) == {"record_id": "r2", "remaining": 1}

    def test_an_edit_that_sends_the_entity_back_unchanged_accepts_nothing(self, labelled_client: TestClient):
        _legacy_entity_edit(labelled_client, "e_car")

        assert _get(labelled_client, "bboxes", "box_car")["review_status"] == "pending"

    def test_moving_an_object_under_another_accepts_nothing(self, labelled_client: TestClient):
        """Its links are not what it says: grouping objects is no edit of what a model found."""
        _legacy_entity_edit(labelled_client, "e_car", parent_id="e_bus")

        assert _get(labelled_client, "bboxes", "box_car")["review_status"] == "pending"


# How many frames a model tracked the objects of `_tracked_dataset` over: one model box per frame.
TRACKED_FRAMES = 30


def _tracked_dataset(frames_of: dict[str, int]) -> Dataset:
    """Objects a model tracked across frames: for each, its tracklet and one pending box per frame."""
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        record=Record,
        entity=LabelledEntity,
        bbox=BBox,
        tracklet=Tracklet,
        views={"image": Image},
    )
    dataset = Dataset.create(Path(tempfile.mkdtemp()) / DATASET_ID, info)
    dataset.add_records({"records": [Record(id="video")]})
    for name, frames in frames_of.items():
        entity_id, tracklet_id = f"e_{name}", f"t_{name}"
        dataset.add_data("entities", [LabelledEntity(id=entity_id, record_id="video", category=name)])
        dataset.add_data(
            "tracklets",
            [
                Tracklet(
                    id=tracklet_id,
                    record_id="video",
                    entity_id=entity_id,
                    start_timestep=0,
                    end_timestep=frames - 1,
                    review_status="pending",
                    **MODEL,
                )
            ],
        )
        dataset.add_data(
            "bboxes",
            [
                BBox(
                    id=f"box_{name}_{frame}",
                    record_id="video",
                    entity_id=entity_id,
                    tracklet_id=tracklet_id,
                    frame_index=frame,
                    view_id="image",
                    coords=BOX_COORDS,
                    format="xywh",
                    is_normalized=True,
                    confidence=MODEL_SCORES[0],
                    review_status="pending",
                    **MODEL,
                )
                for frame in range(frames)
            ],
        )
    return dataset


class TestAnEntityEditOfATrackedObject:
    """A model that tracks an object writes one row per frame, all naming the object: a relabel
    accepts them all at once."""

    def test_the_reference_lookups_do_not_grow_with_the_rows_accepted(self, monkeypatch: pytest.MonkeyPatch):
        """Written through the per-row reference checks, the acceptances would cost lookups per row
        and per reference, under the dataset's write lock: seconds to relabel an object tracked over
        500 frames. An acceptance changes the status alone and cannot break a reference."""
        client = _client(_tracked_dataset({"cat": 1, "fox": TRACKED_FRAMES}))
        lookups: list[str] = []
        find_ids_in_table = Dataset.find_ids_in_table

        def counted(dataset: Dataset, table_name: str, ids: set[str]) -> dict[str, bool]:
            lookups.append(table_name)
            return find_ids_in_table(dataset, table_name, ids)

        monkeypatch.setattr(Dataset, "find_ids_in_table", counted)

        _legacy_entity_edit(client, "e_cat", category="lynx")
        one_frame = len(lookups)
        lookups.clear()
        _legacy_entity_edit(client, "e_fox", category="wolf")

        assert len(lookups) == one_frame
        statuses = {_get(client, "bboxes", f"box_fox_{frame}")["review_status"] for frame in range(TRACKED_FRAMES)}
        assert statuses == {"accepted"}
        assert _get(client, "tracklets", "t_fox")["review_status"] == "accepted"

    def test_a_reference_left_dangling_on_a_row_does_not_fail_the_edit(self):
        """Deleting a tracklet does not delete the rows that name it. Checked, those rows' reference
        would fail the relabel with a 500 after the entity was stored, accepting none of them, and a
        retry, finding the entity already relabelled, would accept nothing either."""
        client = _client(_tracked_dataset({"fox": TRACKED_FRAMES}))
        assert client.delete(f"{BASE}/tracklets/t_fox").status_code == 204

        stored = _legacy_entity_edit(client, "e_fox", category="wolf")

        assert stored["category"] == "wolf"
        statuses = {_get(client, "bboxes", f"box_fox_{frame}")["review_status"] for frame in range(TRACKED_FRAMES)}
        assert statuses == {"accepted"}


# A model's top-2 answer, as a JSONL import with a model source stores it: one score per label.
TOP_LABELS = ["car", "truck"]
TOP_SCORES = [0.6, 0.3]
# A model's answer that gives a label twice, each time with its own score.
TWICE_LABELS = ["car", "truck", "car"]
TWICE_SCORES = [0.6, 0.3, 0.1]


def _put_classification(client: TestClient, row_id: str, body: dict):
    return client.put(f"{BASE}/classifications/{row_id}", json=body, params={"prune_orphan_entity": True})


def _web_body(entity_id: str, labels: list[str], scores: list[float] | None = None) -> dict:
    """The body `buildClassificationBody` sends when the chip is moved to an object: its label,
    scored 1 (classificationPayloadBuilder.ts, `geometryForEntity`)."""
    return {
        "record_id": "r1",
        "entity_id": entity_id,
        "view_id": "image",
        "labels": labels,
        "confidences": WEB_SCORES * len(labels) if scores is None else scores,
        **WEB_SOURCE,
    }


class TestEachKindsScoreIsTheModels:
    """A classification's model score is `confidences`, a box's `confidence`. A score follows what
    it scores: a classification's `confidences[i]` scores its `labels[i]`."""

    def _web_update(self, client: TestClient, entity_id: str, labels: list[str], row_id: str = "cls_car") -> dict:
        resp = _put_classification(client, row_id, _web_body(entity_id, labels))
        assert resp.status_code == 200, resp.text
        return resp.json()

    @staticmethod
    def _with_model_classification(row_id: str, labels: list[str], scores: list[float]) -> TestClient:
        """The car also holds this model's classification, pending."""
        dataset = _labelled_dataset()
        row = _get_row(dataset, "classifications", "cls_car").model_copy(
            update={"id": row_id, "labels": labels, "confidences": scores}
        )
        dataset.add_data("classifications", [row], raise_or_warn="none")
        return _client(dataset)

    @pytest.fixture
    def top_client(self) -> TestClient:
        """The car also holds a model's top-2 classification, pending."""
        return self._with_model_classification("cls_top", TOP_LABELS, TOP_SCORES)

    def test_an_edit_that_changes_only_the_scores_accepts_nothing(self, labelled_client: TestClient):
        stored = self._web_update(labelled_client, "e_car", ["car"])

        assert (stored["review_status"], stored["confidences"]) == ("pending", MODEL_SCORES)
        assert {key: stored[key] for key in MODEL} == MODEL

    def test_a_label_the_person_gives_takes_the_score_sent_with_it(self, labelled_client: TestClient):
        """The model's score of `car` does not score `truck`, which the model never gave."""
        stored = self._web_update(labelled_client, "e_car", ["truck"])

        assert (stored["review_status"], stored["labels"], stored["confidences"]) == (
            "accepted",
            ["truck"],
            WEB_SCORES,
        )
        assert {key: stored[key] for key in MODEL} == MODEL

    def test_a_multi_label_classification_moved_to_an_object_is_saved(self, top_client: TestClient):
        """The interface sends the object's label alone. Were the model's two scores kept for it,
        the row would fail validation, the server would answer 400, and the failed update would stay
        at the head of the interface's queue, failing every later save of the record."""
        stored = self._web_update(top_client, "e_bus", ["bus"], row_id="cls_top")

        assert (stored["entity_id"], stored["review_status"]) == ("e_bus", "accepted")
        assert (stored["labels"], stored["confidences"]) == (["bus"], WEB_SCORES)
        assert _get(top_client, "classifications", "cls_top") == stored

    @pytest.mark.parametrize(
        "labels, sent, kept",
        [
            (["truck"], [1.0], [0.3]),
            (["truck", "car"], [1.0, 1.0], [0.3, 0.6]),
            (["car", "bus"], [1.0, 0.5], [0.6, 0.5]),
            # The model gave `car` once: its score is claimed once, and the second `car` is the
            # person's, scored as sent.
            (["car", "car"], [1.0, 0.5], [0.6, 0.5]),
        ],
        ids=["the model's second label", "reordered", "one label added", "a label given once, repeated"],
    )
    def test_each_label_the_model_gave_keeps_the_model_score(
        self, top_client: TestClient, labels: list[str], sent: list[float], kept: list[float]
    ):
        resp = _put_classification(top_client, "cls_top", _web_body("e_car", labels, sent))

        assert resp.status_code == 200, resp.text
        assert (resp.json()["review_status"], resp.json()["labels"], resp.json()["confidences"]) == (
            "accepted",
            labels,
            kept,
        )

    def test_a_label_the_model_gave_twice_keeps_both_scores_in_the_model_order(self):
        """Each of the model's scores is claimed once. Claimed again, the first `car`'s score would
        score both, and the model's score of the second would be lost."""
        client = self._with_model_classification("cls_twice", TWICE_LABELS, TWICE_SCORES)
        reordered = ["car", "car", "truck"]

        resp = _put_classification(client, "cls_twice", _web_body("e_car", reordered))

        assert resp.status_code == 200, resp.text
        first_car, truck, second_car = TWICE_SCORES
        assert (resp.json()["labels"], resp.json()["confidences"]) == (reordered, [first_car, second_car, truck])

    @pytest.mark.parametrize(
        "sent",
        [None, [1.0], [1.0, 0.5, 0.2]],
        ids=["no scores", "fewer scores than labels", "more scores than labels"],
    )
    def test_a_label_added_without_its_score_is_refused(self, top_client: TestClient, sent: list[float] | None):
        """Nothing scores the new label: the model's scores would be left scoring other labels. The
        scores sent are read by position only when there is one per label, as the schema requires:
        read regardless, a shorter list would fail the server with a 500 instead of this answer."""
        body = _web_body("e_car", ["car", "bus"])
        if sent is None:
            del body["confidences"]
        else:
            body["confidences"] = sent

        resp = _put_classification(top_client, "cls_top", body)

        assert resp.status_code == 400
        assert "'bus'" in resp.json()["detail"]
        stored = _get(top_client, "classifications", "cls_top")
        assert (stored["labels"], stored["confidences"], stored["review_status"]) == (
            TOP_LABELS,
            TOP_SCORES,
            "pending",
        )


# The spec version of a dataset whose annotation tables have no review status yet.
SPEC_VERSION_BEFORE_REVIEW = 2


def _without_status_column(dataset: Dataset, table_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put a table back at the layout before review statuses, as a library that could not migrate.

    The dataset says it is at spec version 2, and the migration that would add the column fails,
    as on a read-only library: the dataset opens at the old layout (`Dataset.__init__`).
    """
    dataset.open_table(table_name).drop_columns(["review_status"])
    info_file = dataset.path / "info.json"
    info_json = json.loads(info_file.read_text(encoding="utf-8"))
    info_json["spec_version"] = SPEC_VERSION_BEFORE_REVIEW
    info_file.write_text(json.dumps(info_json), encoding="utf-8")

    def read_only(_dataset: Dataset) -> None:
        raise PermissionError("read-only library")

    monkeypatch.setattr(Dataset, "_migrate_storage", read_only)


class TestDatasetThatCouldNotMigrate:
    """A table without the status column: a decision cannot be stored in it, so its rows are
    outside the review. The API still answers."""

    def test_the_queue_skips_a_table_without_the_column(self, dataset: Dataset, monkeypatch: pytest.MonkeyPatch):
        _without_status_column(dataset, "masks", monkeypatch)
        client = _client(dataset)

        # r5's only pending row is a mask. r1 and r3 hold pending boxes.
        assert _next(client) == {"record_id": "r1", "remaining": 2}
        assert "review_status" not in Dataset(dataset.path).open_table("masks").schema.names

    def test_an_entity_edit_accepts_nothing_in_a_table_without_the_column(self, monkeypatch: pytest.MonkeyPatch):
        dataset = _labelled_dataset()
        _without_status_column(dataset, "bboxes", monkeypatch)
        client = _client(dataset)
        boxes_version = Dataset(dataset.path).open_table("bboxes").version

        resp = client.put(f"{BASE}/entities/e_car", json={"category": "truck"})

        assert resp.status_code == 200, resp.text
        assert resp.json()["category"] == "truck"
        # Nothing is written to a table that cannot hold the decision.
        assert Dataset(dataset.path).open_table("bboxes").version == boxes_version
        assert _get(client, "bboxes", "box_car")["coords"] == BOX_COORDS
        # The classifications table has the column: its row is accepted as anywhere else.
        assert _get(client, "classifications", "cls_car")["review_status"] == "accepted"
