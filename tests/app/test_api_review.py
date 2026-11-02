# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review of a model's annotations through the API, beyond one box's update.

Each kind's own score stays the model's through a person's edit, following what it scores.
"""

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, Classification, Entity, Image, Record


DATASET_ID = "review"
BASE = f"/datasets/{DATASET_ID}"

MODEL = {"source_type": "model", "source_name": "detection", "source_metadata": '{"model": "yolo"}'}
HUMAN = {"source_type": "ground_truth", "source_name": "Ground Truth"}

RECORD_IDS = ["r1", "r2"]


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


# Each kind's score, through a person's edit
# ==========================================

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
