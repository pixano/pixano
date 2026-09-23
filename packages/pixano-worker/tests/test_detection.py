# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The detection kind: where its boxes land, what it does with each failure, and what it leaves
to the boxes a person drew or reviewed."""

import io
import json
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image as PILImage
from pixano_inference_client import PixanoInferenceError
from pixano_worker.kinds import MODEL_TASK_MARKER, DetectionKind, TransientError
from pixano_worker.kinds.detection import iou
from pixano_worker.media import ResolvedMedia
from pixano_worker.writer import JobWriter, ModelIdentity


WIDTH, HEIGHT = 200, 100


class _Inference:
    """An inference that answers, for each image, the boxes a test gave it."""

    def __init__(self) -> None:
        self.answers: dict[str, list[tuple[list[int], float, str]]] = {}
        self.bad: set[str] = set()
        self.status_for_everything: int | None = None
        self.calls: list[Any] = []

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def list_models(self) -> list[Any]:
        return [SimpleNamespace(name="yolo", model_path="yolo26s.pt", capability="detection")]

    def detection(self, request: Any, **_kwargs: Any) -> Any:
        self.calls.append(request)
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, "error", "refused")
        if request.image in self.bad:
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        found = self.answers.get(request.image, [])
        return SimpleNamespace(
            data=SimpleNamespace(
                boxes=[box for box, _, _ in found],
                scores=[score for _, score, _ in found],
                classes=[name for _, _, name in found],
            )
        )


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height)).save(buffer, format="PNG")
    return buffer.getvalue()


class _Reader:
    """Images of 200 × 100 pixels, designated by path; some missing, some whose size the dataset
    does not record, some of those unreadable."""

    def __init__(
        self,
        missing: set[str] = frozenset(),  # type: ignore[assignment]
        unsized: set[str] = frozenset(),  # type: ignore[assignment]
        unreadable: set[str] = frozenset(),  # type: ignore[assignment]
    ) -> None:
        self.missing, self.unsized, self.unreadable = missing, unsized, unreadable
        self.dataset = SimpleNamespace(
            get_view_binary=self._get_view_binary,
            info=SimpleNamespace(tables={"bboxes": object, "entities": object, "images": object}),
        )

    def _get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str]:
        return (b"not an image" if row_id in self.unreadable else _png(WIDTH, HEIGHT)), "image/png"

    def open_media(self, table_name: str, view: Any) -> Any:
        return io.BytesIO(self._get_view_binary(table_name, view.id)[0])

    def rows(self, table_name: str, ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(
                id=view_id,
                record_id=f"rec-{view_id}",
                uri=f"/medias/{view_id}.jpg",
                width=0 if view_id in self.unsized else WIDTH,
                height=0 if view_id in self.unsized else HEIGHT,
            )
            for view_id in ids
            if view_id not in self.missing
        ]

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        return ResolvedMedia(view.uri, carried_bytes=False, reason="path")


@pytest.fixture
def inference(monkeypatch: pytest.MonkeyPatch) -> _Inference:
    fake = _Inference()
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", fake.client)
    return fake


KIND = DetectionKind("http://inference", "")
PARAMS = KIND.validate_params({"model": "yolo"})


def _process(reader: _Reader, view_ids: list[str], params: Any = PARAMS) -> tuple[dict[str, Any], Any]:
    payload = {"table": "images", "view_ids": view_ids}
    result = KIND.process(reader, payload, params)  # type: ignore[arg-type]
    return result, KIND.outcome(result, payload, len(view_ids))


class TestParameters:
    def test_names_no_model_and_asks_the_form_for_a_served_one(self) -> None:
        schema = KIND.params_schema()

        assert "model" in schema["required"]
        assert schema["properties"]["model"][MODEL_TASK_MARKER] == "detection"

    def test_replacing_the_previous_boxes_is_confirmed(self) -> None:
        from pixano_worker.kinds import CONFIRM_MARKER

        assert CONFIRM_MARKER in KIND.params_schema()["properties"]["replace_previous"]

    def test_an_overlap_threshold_of_zero_is_refused(self) -> None:
        """At zero every detection would overlap every box, and none would be written."""
        with pytest.raises(ValueError):
            KIND.validate_params({"model": "yolo", "overlap_threshold": 0})


class TestPlacement:
    def test_pixel_corners_become_a_normalised_top_left_and_size(self, inference: _Inference) -> None:
        inference.answers["/medias/a.jpg"] = [([20, 10, 120, 60], 0.9, "car")]

        result, _ = _process(_Reader(), ["a"])

        assert result["media"][0]["boxes"] == [[0.1, 0.1, 0.5, 0.5]]

    def test_a_box_past_the_image_is_cut_at_its_edge(self, inference: _Inference) -> None:
        inference.answers["/medias/a.jpg"] = [([-10, -5, 250, 150], 0.9, "car")]

        result, _ = _process(_Reader(), ["a"])

        assert result["media"][0]["boxes"] == [[0.0, 0.0, 1.0, 1.0]]

    def test_a_box_reduced_to_nothing_is_not_one(self, inference: _Inference) -> None:
        inference.answers["/medias/a.jpg"] = [([300, 10, 400, 60], 0.9, "car"), ([10, 10, 10, 60], 0.8, "dog")]

        result, _ = _process(_Reader(), ["a"])

        assert result["media"][0]["boxes"] == []

    def test_the_classes_asked_for_are_sent_and_none_means_the_models_own(self, inference: _Inference) -> None:
        _process(_Reader(), ["a"])
        _process(_Reader(), ["a"], KIND.validate_params({"model": "yolo", "classes": ["zebra"]}))

        assert [request.classes for request in inference.calls] == [None, ["zebra"]]


class TestFailures:
    def test_a_medium_the_server_refuses_costs_only_itself(self, inference: _Inference) -> None:
        inference.bad = {"/medias/b.jpg"}

        _, outcome = _process(_Reader(), ["a", "b", "c"])

        assert outcome.produced == 2
        assert [(item.item_id, item.detail["record_id"]) for item in outcome.quarantined] == [("b", "rec-b")]

    def test_a_medium_where_the_model_sees_nothing_is_produced(self, inference: _Inference) -> None:
        """No box is an answer: it replaces what a previous run had found there."""
        _, outcome = _process(_Reader(), ["a"])

        assert outcome.produced == 1

    def test_a_size_the_dataset_does_not_record_is_read_from_the_image(self, inference: _Inference) -> None:
        """A dataset imported by URI records no size; its boxes are placed all the same."""
        inference.answers["/medias/a.jpg"] = [([20, 10, 120, 60], 0.9, "car")]

        result, outcome = _process(_Reader(unsized={"a"}), ["a"])

        assert outcome.quarantined == []
        assert result["media"][0]["boxes"] == [[0.1, 0.1, 0.5, 0.5]]

    def test_the_size_of_an_image_imported_by_uri_is_read_from_its_file(
        self, inference: _Inference, tmp_path: Any
    ) -> None:
        """Independent review of lot 2, B1: such a view carries no bytes, and the first version
        of this fallback read only bytes — every image of voc_2007_uri went to quarantine."""
        from pixano_worker.media import MediaResolver
        from pixano_worker.reader import JobReader

        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas import BBox, Entity, Image, Record

        media = tmp_path / "media"
        media.mkdir()
        (media / "a.png").write_bytes(_png(WIDTH, HEIGHT))
        dataset = Dataset.create(
            tmp_path / "ds",
            DatasetInfo(id="ds", name="ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
        )
        dataset.add_records({"records": [Record(id="r1")]})
        dataset.add_data(
            "images",
            [Image(id="a", record_id="r1", logical_name="image", uri=str(media / "a.png"), width=0, height=0)],
            raise_or_warn="none",
        )
        reader = JobReader(lambda: dataset, MediaResolver(str(media), "/inference-media"))
        inference.answers["/inference-media/a.png"] = [([20, 10, 120, 60], 0.9, "car")]

        result, outcome = _process(reader, ["a"])  # type: ignore[arg-type]

        assert outcome.quarantined == []
        assert result["media"][0]["boxes"] == [[0.1, 0.1, 0.5, 0.5]]

    def test_a_medium_whose_size_cannot_be_known_is_quarantined_without_a_call(self, inference: _Inference) -> None:
        """Its boxes could not be placed: they are stored relative to its size."""
        _, outcome = _process(_Reader(unsized={"a"}, unreadable={"a"}), ["a", "b"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("a", "image size unknown")]
        assert len(inference.calls) == 1

    def test_a_missing_medium_is_quarantined(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader(missing={"a"}), ["a", "b"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("a", "media not found")]

    @pytest.mark.parametrize("status", [0, 503])
    def test_a_server_that_does_not_answer_makes_the_chunk_transient(self, inference: _Inference, status: int) -> None:
        inference.status_for_everything = status

        with pytest.raises(TransientError):
            _process(_Reader(), ["a", "b"])

    def test_a_request_that_can_never_pass_fails_the_chunk(self, inference: _Inference) -> None:
        inference.status_for_everything = 404

        with pytest.raises(PixanoInferenceError):
            _process(_Reader(), ["a"])

    def test_a_server_that_refuses_everything_even_the_witness_is_not_the_medias_fault(
        self, inference: _Inference
    ) -> None:
        """A chunk of one image, all refused: the witness image tells the server's fault apart."""
        inference.status_for_everything = 500

        with pytest.raises(TransientError, match="witness"):
            _process(_Reader(), ["a"])


class TestIou:
    def test_the_same_box(self) -> None:
        assert iou((0, 0, 1, 1), (0, 0, 1, 1)) == 1

    def test_disjoint_boxes(self) -> None:
        assert iou((0, 0, 0.1, 0.1), (0.5, 0.5, 1, 1)) == 0

    def test_half_a_box(self) -> None:
        assert iou((0, 0, 1, 1), (0, 0, 0.5, 1)) == 0.5


class TestPlanning:
    def test_a_dataset_without_a_box_table_is_refused(self, inference: _Inference) -> None:
        reader = _Reader()
        reader.dataset.info.tables = {"entities": object, "images": object}

        with pytest.raises(ValueError, match="'bboxes'"):
            list(KIND.plan(reader, PARAMS))  # type: ignore[arg-type]

    def test_a_model_the_server_does_not_serve_is_refused_with_those_it_does(self, inference: _Inference) -> None:
        with pytest.raises(ValueError, match="serves yolo"):
            list(KIND.plan(_Reader(), KIND.validate_params({"model": "grounding-dino"})))  # type: ignore[arg-type]


class TestAgainstRealLance:
    """What a detection writes next to the boxes already there."""

    @pytest.fixture
    def scene(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas import BBox, Entity, Image, Record

        dataset = Dataset.create(
            tmp_path / "scene",
            DatasetInfo(id="scene", name="Scene", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
        )
        dataset.add_records({"records": [Record(id="r1")]})
        return dataset

    @staticmethod
    def _writer(scene, job_id: str = "job-1") -> JobWriter:
        return JobWriter(
            lambda: scene, "detection", job_id, "model", params={"model": "yolo"}, model=ModelIdentity("yolo")
        )

    def _detect(self, scene, found: list[tuple[list[float], str]], **params: Any) -> None:
        """A chunk of one medium, `v1`, where the model found these normalised xywh boxes."""
        writer = self._writer(scene)
        KIND.prepare(writer, KIND.validate_params({"model": "yolo", **params}))
        medium = {
            "view_id": "v1",
            "record_id": "r1",
            "width": WIDTH,
            "height": HEIGHT,
            "boxes": [coords for coords, _ in found],
            "scores": [0.9] * len(found),
            "classes": [name for _, name in found],
        }
        KIND.write(
            writer,
            {"media": [medium], "quarantined": []},
            {},
            KIND.validate_params({"model": "yolo", **params}),  # type: ignore[arg-type]
        )

    @staticmethod
    def _person_draws(scene, box_id: str, coords: list[float], name: str, **fields: Any) -> None:
        """A box a person drew, with its object — in pixels and corners, as a hand import may be."""
        from pixano.schemas import BBox

        scene.add_data("entities", [scene.info.entity(id=f"e-{box_id}", record_id="r1", category=name)])
        scene.add_data(
            "bboxes",
            [
                BBox(
                    id=box_id,
                    record_id="r1",
                    view_id="v1",
                    entity_id=f"e-{box_id}",
                    coords=coords,
                    format="xyxy",
                    is_normalized=False,
                    source_type="human",
                    **fields,
                )
            ],
        )

    @staticmethod
    def _boxes(scene) -> dict[str, tuple[str, str]]:
        """Each box's class and who wrote it."""
        classes = {entity.id: entity.category for entity in scene.get_data("entities", limit=None)}
        return {
            box.id: (classes.get(box.entity_id, ""), box.source_type) for box in scene.get_data("bboxes", limit=None)
        }

    # The person's box covers the left half of the image: (0, 0) to (100, 100) pixels.
    PERSON = [0.0, 0.0, 100.0, 100.0]
    # The same object, seen by the model a little larger: IoU 0.8 with the person's box.
    SAME = [0.0, 0.0, 0.5 / 0.8, 1.0]

    def test_writes_each_box_with_its_object_pending_review(self, scene) -> None:
        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car")])

        (box,) = scene.get_data("bboxes", limit=None)
        assert (box.format, box.is_normalized, box.review_status, box.confidence) == ("xywh", True, "pending", 0.9)
        assert json.loads(box.source_metadata)["model"] == "yolo"
        assert self._boxes(scene) == {box.id: ("car", "model")}

    def test_a_detection_over_a_persons_box_of_the_same_class_is_not_written(self, scene) -> None:
        self._detect(scene, [])  # the class field appears with the first detection job
        self._person_draws(scene, "h1", self.PERSON, "car")

        self._detect(scene, [(self.SAME, "Car")])

        assert self._boxes(scene) == {"h1": ("car", "human")}

    def test_a_detection_of_another_class_is_written(self, scene) -> None:
        self._detect(scene, [])
        self._person_draws(scene, "h1", self.PERSON, "person")

        self._detect(scene, [(self.SAME, "bicycle")])

        assert sorted(self._boxes(scene).values()) == [("bicycle", "model"), ("person", "human")]

    def test_a_persons_box_without_a_class_stands_for_every_class(self, scene) -> None:
        self._detect(scene, [])
        self._person_draws(scene, "h1", self.PERSON, "")

        self._detect(scene, [(self.SAME, "bicycle")])

        assert self._boxes(scene) == {"h1": ("", "human")}

    def test_below_the_threshold_it_is_written(self, scene) -> None:
        self._detect(scene, [])
        self._person_draws(scene, "h1", self.PERSON, "car")

        self._detect(scene, [(self.SAME, "car")], overlap_threshold=0.9)

        assert len(self._boxes(scene)) == 2

    def test_a_box_a_person_rejected_keeps_the_model_from_proposing_it_again(self, scene) -> None:
        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car")])
        (box,) = scene.get_data("bboxes", limit=None)
        box.review_status = "rejected"
        scene.update_data("bboxes", [box])

        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car")])

        assert [row.review_status for row in scene.get_data("bboxes", limit=None)] == ["rejected"]

    def test_its_own_pending_boxes_do_not_hold_it_back(self, scene) -> None:
        """A rerun replaces them: they are no person's word."""
        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car")])

        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car")])

        assert len(self._boxes(scene)) == 1

    def test_replacing_the_previous_boxes_spares_what_a_person_reviewed(self, scene) -> None:
        self._detect(scene, [([0.1, 0.1, 0.2, 0.2], "car"), ([0.5, 0.5, 0.2, 0.2], "dog")])
        first, _ = scene.get_data("bboxes", limit=None)
        first.review_status = "accepted"
        scene.update_data("bboxes", [first])
        other_model = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("other"))
        other_model.replace(
            "bboxes",
            "v1",
            [
                scene.info.tables["bboxes"](
                    **{**first.model_dump(), "id": "", "review_status": "", **other_model.provenance()}
                )
            ],
            [scene.info.entity(id="", record_id="r1", category="cat")],
        )

        self._detect(scene, [], replace_previous=True)

        assert [row.id for row in scene.get_data("bboxes", limit=None)] == [first.id]
        assert len(scene.get_data("entities", limit=None)) == 1
