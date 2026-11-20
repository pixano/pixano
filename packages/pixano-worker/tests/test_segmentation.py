# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The segmentation kind: which boxes it asks about, what it does with each answer, and what it
leaves to the masks a person drew or accepted.

The dataset is a real one, read and written through the runner's own reader and writer; only the
inference is a stand-in — answering at the client for most tests, and at the HTTP edge with
bodies the real server returned for the tests of what it answers.
"""

import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import httpx
import numpy as np
import pytest
from PIL import Image as PILImage
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_worker import runner
from pixano_worker.kinds import CONFIRM_MARKER, MODEL_TASK_MARKER, SegmentationKind, TransientError
from pixano_worker.kinds.inference import witness_image
from pixano_worker.kinds.segmentation import (
    IMAGE_SIZE_UNKNOWN,
    MASK_SIZE_DIFFERS,
    NO_BOX_TO_SEGMENT,
    SEGMENTATION_CAPABILITY,
    UNREADABLE_MASK,
    WITNESS_PROMPT,
    WRONG_MASK_COUNT,
)
from pixano_worker.media import MediaResolver
from pycocotools import mask as mask_api

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record


DATASET_ID = "shapes"
# Not square, so that a mask whose height and width were swapped would not fit its image.
WIDTH, HEIGHT = 200, 100
# The two segmentation models the inference serves, and the detector it serves beside them.
TINY, SMALL = "sam2.1-tiny", "sam2.1-small"
DETECTOR = "yolo"
CHECKPOINTS = {TINY: "facebook/sam2.1-hiera-tiny", SMALL: "facebook/sam2.1-hiera-small", DETECTOR: "yolo26n.pt"}
# The same media storage, mounted elsewhere by the inference: the worker sends it this path.
INFERENCE_MEDIA_ROOT = "/inference-media"
# The field the entities hold a class in, as a detection job gives it to them.
CLASS_FIELD = "category"

# Where things are on the images, in pixels: left, top, right, bottom.
CAR_PX = (20, 10, 60, 50)
# A corner of the car, a tenth of it.
CAR_CORNER_PX = (20, 10, 30, 26)
DOG_PX = (120, 40, 180, 90)


class _Inference:
    """An inference serving two segmentation models and a detector.

    For each box, it answers one mask filling the box, on the grid of the image it was sent.
    """

    def __init__(self, sizes: dict[str, tuple[int, int]]) -> None:
        self.sizes = sizes
        self.calls: list[Any] = []
        self.bad: set[str] = set()
        self.status_for_everything: int | None = None
        self.code_for_everything = "error"
        # Rewrites the answer for a test: given the request and the masks, the masks to send back.
        self.answer: Callable[[Any, list[list[Any]]], list[list[Any]]] | None = None
        self.opened = self.closed = 0

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        self.opened += 1
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.closed += 1

    def list_models(self) -> list[Any]:
        return [
            SimpleNamespace(name=TINY, model_path=CHECKPOINTS[TINY], capability=SEGMENTATION_CAPABILITY),
            SimpleNamespace(name=SMALL, model_path=CHECKPOINTS[SMALL], capability=SEGMENTATION_CAPABILITY),
            SimpleNamespace(name=DETECTOR, model_path=CHECKPOINTS[DETECTOR], capability="detection"),
        ]

    def segmentation(self, request: Any, **_kwargs: Any) -> Any:
        self.calls.append(request)
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, self.code_for_everything, "refused")
        if request.image in self.bad:
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        width, height = self.sizes.get(request.image, (WIDTH, HEIGHT))
        masks = [[_rectangle(box, width, height)] for box in request.boxes]
        if self.answer is not None:
            masks = self.answer(request, masks)
        return SimpleNamespace(data=SimpleNamespace(masks=masks))


def _rle(corners: tuple[int, int, int, int] | list[int], width: int, height: int) -> dict[str, Any]:
    """A mask filling a box, as pycocotools compresses it: its grid is [height, width]."""
    left, top, right, bottom = corners
    pixels = np.zeros((height, width), dtype=np.uint8, order="F")
    pixels[top:bottom, left:right] = 1
    encoded = mask_api.encode(pixels)
    return {"size": list(encoded["size"]), "counts": encoded["counts"]}


def _rectangle(corners: list[int], width: int, height: int) -> Any:
    return SimpleNamespace(**_rle(corners, width, height))


def _bounds(mask: Any) -> list[int]:
    """The pixel corners of what a stored mask paints."""
    x, y, w, h = mask_api.toBbox({"size": list(mask.size), "counts": mask.counts})
    return [int(x), int(y), int(x + w), int(y + h)]


@dataclass
class _Scene:
    """A library holding one dataset of images on disk, with boxes and objects but no masks table."""

    library: Path
    media: MediaResolver
    inference: _Inference
    kind: SegmentationKind

    @property
    def path(self) -> Path:
        return self.library / DATASET_ID

    def as_a_person(self) -> Dataset:
        """The dataset as the application opens it: an instance of its own."""
        return Dataset.find(DATASET_ID, self.library)

    def as_the_worker(self) -> Dataset:
        """The instance the worker's chunks read and write through: a same-process change."""
        return runner._open_dataset(self.library, DATASET_ID)

    def reader(self, fresh: bool = False) -> Any:
        return runner._reader_for(self.library, DATASET_ID, self.media, fresh=fresh)

    def writer(self, params: Any, job_id: str = "job-1") -> Any:
        return runner._writer_for(self.library, DATASET_ID, self.kind, job_id, params)

    def plan(self, params: Any, job_id: str = "job-1") -> list[Any]:
        """Plan a job as the runner does: split on the dataset reopened, then prepared under its write lock."""
        return runner._plan_and_prepare(
            self.kind, self.library, DATASET_ID, self.media, job_id, params, threading.Event()
        )


#: The scene's images: each view, its record, its file and its size as the dataset records it.
IMAGES = {
    "v1": ("r1", "a.png", (WIDTH, HEIGHT)),
    "v2": ("r2", "b.png", (WIDTH, HEIGHT)),
}


def _make_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, images: dict[str, tuple[str, str, tuple[int, int]]]
) -> tuple[Path, Path]:
    """A dataset of these images, created without a masks table; its library and media root."""
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay
    # independent of each other.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Shapes", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )
    dataset.add_records({"records": [Record(id=record_id) for record_id, _, _ in dict.fromkeys(images.values())]})
    rows = []
    for view_id, (record_id, file_name, (width, height)) in images.items():
        PILImage.new("RGB", (width, height)).save(media_root / file_name)
        rows.append(
            Image(
                id=view_id,
                record_id=record_id,
                logical_name="image",
                uri=str(media_root / file_name),
                width=width,
                height=height,
            )
        )
    dataset.add_data("images", rows, raise_or_warn="none")
    # The class field a detection job gives the entities.
    dataset.ensure_entity_text_field(CLASS_FIELD)
    return library, media_root


@pytest.fixture
def scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Scene:
    library, media_root = _make_scene(tmp_path, monkeypatch, IMAGES)
    inference = _Inference({f"{INFERENCE_MEDIA_ROOT}/{file_name}": size for _, file_name, size in IMAGES.values()})
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", inference.client)
    media = MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT)
    return _Scene(library, media, inference, SegmentationKind("http://inference"))


def _record_of(view_id: str) -> str:
    return IMAGES[view_id][0]


def _entity(dataset: Dataset, **fields: Any) -> Any:
    """An entity row of the dataset's own entity schema, which a dataset with entities always has."""
    schema = dataset.info.entity
    assert schema is not None
    return schema(**fields)


def _box(
    dataset: Dataset,
    box_id: str,
    view_id: str,
    corners: tuple[int, int, int, int],
    name: str = "car",
    *,
    entity_id: str | None = None,
    source_type: str = "human",
    review_status: str = "",
    in_pixels: bool = False,
) -> str:
    """A box and the object it names, if that object does not exist yet; the object's id.

    Normalised top-left and size, as the interface and detection store them, or pixel corners,
    as a hand import may.
    """
    entity_id = f"e-{box_id}" if entity_id is None else entity_id
    if entity_id and not dataset.get_data("entities", ids=[entity_id]):
        dataset.add_data(
            "entities",
            [_entity(dataset, id=entity_id, record_id=_record_of(view_id), **{CLASS_FIELD: name})],
        )
    left, top, right, bottom = corners
    if in_pixels:
        coords, layout = [float(value) for value in corners], "xyxy"
    else:
        coords, layout = [left / WIDTH, top / HEIGHT, (right - left) / WIDTH, (bottom - top) / HEIGHT], "xywh"
    dataset.add_data(
        "bboxes",
        [
            BBox(
                id=box_id,
                record_id=_record_of(view_id),
                view_id=view_id,
                entity_id=entity_id,
                coords=coords,
                format=layout,
                is_normalized=not in_pixels,
                source_type=source_type,
                review_status=review_status,
            )
        ],
    )
    return entity_id


def _person_masks(
    dataset: Dataset,
    mask_id: str,
    view_id: str,
    entity_id: str,
    corners: tuple[int, int, int, int],
    *,
    source_type: str = "human",
    review_status: str = "",
    model: str | None = None,
) -> None:
    """A mask filling these corners, on an object: a person's, or a model's when a model is named."""
    dataset.ensure_annotation_table("mask")
    metadata = json.dumps({"kind": "segmentation", "model": model} if model else {})
    dataset.add_data(
        "masks",
        [
            CompressedRLE(
                id=mask_id,
                record_id=_record_of(view_id),
                view_id=view_id,
                entity_id=entity_id,
                **_rle(corners, WIDTH, HEIGHT),
                source_type=source_type,
                source_name="segmentation" if model else "",
                source_metadata=metadata,
                review_status=review_status,
            )
        ],
    )


def _params(scene: _Scene, **params: Any) -> Any:
    return scene.kind.validate_params({"model": TINY, **params})


def _run(scene: _Scene, job_id: str = "job-1", **params: Any) -> list[Any]:
    """One job as the runner runs it, without the queue: planned by the runner itself — split on the
    dataset reopened, then prepared under the dataset's write lock —, then each chunk processed and
    written through the runner's reader and writer.

    Returns:
        Each chunk's outcome.
    """
    checked = _params(scene, **params)
    chunks = scene.plan(checked, job_id)
    outcomes = []
    for chunk in chunks:
        result = scene.kind.process(scene.reader(), chunk.payload, checked)
        outcomes.append(scene.kind.outcome(result, chunk.payload, chunk.task_count))
        scene.kind.write(scene.writer(checked, job_id), result, chunk.payload, checked)
    return outcomes


def _process(scene: _Scene, view_ids: list[str], **params: Any) -> tuple[dict[str, Any], Any]:
    """One chunk of these views, processed: its result and its outcome."""
    payload = {"table": "images", "view_ids": view_ids}
    result = scene.kind.process(scene.reader(), payload, _params(scene, **params))
    return result, scene.kind.outcome(result, payload, len(view_ids))


def _masks(scene: _Scene) -> list[CompressedRLE]:
    """Every mask of the dataset, read through an instance opened now."""
    dataset = Dataset(scene.path)
    return dataset.get_data("masks", limit=None) if "masks" in dataset.info.tables else []


def _model_of(mask: Any) -> str:
    """The model a row's provenance names, "" for a row no model wrote."""
    return str(json.loads(mask.source_metadata).get("model") or "")


def _summary(scene: _Scene) -> list[tuple[str, str, str, str]]:
    """Each mask's object, model, status and source, sorted."""
    return sorted((mask.entity_id, _model_of(mask), mask.review_status, mask.source_type) for mask in _masks(scene))


class TestParameters:
    def test_names_no_model_and_asks_the_form_for_a_segmentation_one(self) -> None:
        """The form lists the models of Pixano's task, which the inference calls `segmentation`."""
        schema = SegmentationKind().params_schema()

        assert "model" in schema["required"]
        assert schema["properties"]["model"][MODEL_TASK_MARKER] == "image_mask_generation"

    def test_replacing_the_previous_masks_is_confirmed(self) -> None:
        assert CONFIRM_MARKER in SegmentationKind().params_schema()["properties"]["replace_previous"]

    @pytest.mark.parametrize("threshold", [0, 1.5])
    def test_an_overlap_threshold_outside_zero_to_one_is_refused(self, threshold: float) -> None:
        """At zero every mask would cover every other, and none would be written."""
        with pytest.raises(ValueError):
            SegmentationKind().validate_params({"model": TINY, "overlap_threshold": threshold})

    def test_the_provenance_records_what_was_computed_not_how_the_engine_ran(self) -> None:
        kind = SegmentationKind()

        recorded = kind.provenance_params(kind.validate_params({"model": TINY, "replace_previous": True}))

        assert set(recorded) == {"model", "media", "overlap_threshold"}


class _Tables:
    """A reader whose dataset holds these tables and nothing else: planning stops at their check."""

    def __init__(self, *tables: str) -> None:
        self.dataset = SimpleNamespace(info=SimpleNamespace(tables=dict.fromkeys(tables, object)))


class TestPlanning:
    def test_a_dataset_without_a_masks_table_is_planned_on_every_image(self, scene: _Scene) -> None:
        """A dataset imported with boxes only has none: the job gives it one rather than refusing."""
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)

        chunks = list(scene.kind.plan(scene.reader(fresh=True), _params(scene)))

        assert "masks" not in Dataset(scene.path).info.tables
        assert [chunk.payload for chunk in chunks] == [{"table": "images", "view_ids": ["v1", "v2"]}]

    def test_a_media_type_it_cannot_send_refuses_the_job(self, scene: _Scene) -> None:
        with pytest.raises(ValueError, match="cannot process video"):
            list(scene.kind.plan(scene.reader(fresh=True), _params(scene, media=["image", "video"])))

    @pytest.mark.parametrize("missing", ["bboxes", "entities"])
    def test_a_dataset_without_boxes_or_objects_is_refused(self, missing: str) -> None:
        reader = _Tables(*({"bboxes", "entities", "images"} - {missing}))

        with pytest.raises(ValueError, match=f"'{missing}'"):
            list(SegmentationKind().plan(reader, SegmentationKind().validate_params({"model": TINY})))  # type: ignore[arg-type]

    @pytest.mark.parametrize("boxes", ["none", "naming no object"])
    def test_a_dataset_with_no_box_to_segment_is_refused(self, scene: _Scene, boxes: str) -> None:
        """A job that would skip every image is better refused with the reason."""
        dataset = scene.as_a_person()
        if boxes == "naming no object":
            _box(dataset, "b1", "v1", CAR_PX, entity_id="")

        with pytest.raises(ValueError, match=NO_BOX_TO_SEGMENT):
            list(scene.kind.plan(scene.reader(fresh=True), _params(scene)))

    def test_clearing_the_previous_masks_needs_no_box(self, scene: _Scene) -> None:
        """Once every box is deleted, `replace_previous` is the only way to clear the masks the
        model left pending; refusing it would leave them for good."""
        assert list(scene.kind.plan(scene.reader(fresh=True), _params(scene, replace_previous=True)))

    def test_a_model_served_for_another_task_is_refused_with_those_served_for_this_one(self, scene: _Scene) -> None:
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)

        with pytest.raises(ValueError, match=f"serves {SMALL}, {TINY}"):
            list(scene.kind.plan(scene.reader(fresh=True), _params(scene, model=DETECTOR)))

    def test_a_refused_job_clears_nothing(self, scene: _Scene) -> None:
        """The runner prepares only after a plan that produced work: everything that can refuse
        the job refuses it before the pending masks are cleared."""
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)
        _run(scene)
        before = _summary(scene)

        with pytest.raises(ValueError, match="serves"):
            list(scene.kind.plan(scene.reader(fresh=True), _params(scene, model=DETECTOR, replace_previous=True)))

        assert before == [("e-b1", TINY, "pending", "model")]
        assert _summary(scene) == before


class TestTheRequest:
    def test_one_call_per_image_with_its_boxes_in_whole_pixels_sorted_by_box_id(self, scene: _Scene) -> None:
        """Rounded to the nearest pixel, cut at the image, one mask per box, a predictor reset."""
        dataset = scene.as_a_person()
        # Stored in pixels, a corner past the image, by a hand import.
        _box(dataset, "b2", "v1", (150, 40, 230, 90), in_pixels=True)
        # Stored normalised, a model's pending box: 0.29 × 100 is 28.999…, which is pixel 29.
        _box(dataset, "b1", "v1", (20, 29, 60, 50), source_type="model", review_status="pending")

        _, outcome = _process(scene, ["v1"])

        (request,) = scene.inference.calls
        assert outcome.produced == 1
        assert request.image == f"{INFERENCE_MEDIA_ROOT}/a.png"
        assert request.model == TINY
        assert request.boxes == [[20, 29, 60, 50], [150, 40, 200, 90]]
        assert (request.multimask_output, request.num_multimask_outputs, request.reset_predictor) == (False, 1, True)

    def test_a_box_naming_nothing_is_not_sent(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        _box(dataset, "b1", "v1", CAR_PX)
        _box(dataset, "b3", "v1", DOG_PX, entity_id="")
        _box(dataset, "b4", "v1", DOG_PX, review_status="")
        dataset.delete_data("entities", ["e-b4"])

        _process(scene, ["v1"])

        assert [request.boxes for request in scene.inference.calls] == [[list(CAR_PX)]]

    def test_every_status_of_a_box_prompts(self, scene: _Scene) -> None:
        """A model's box still to review prompts too: masks arrive right after a detection."""
        dataset = scene.as_a_person()
        statuses = ("pending", "accepted")
        for n, status in enumerate(statuses):
            _box(dataset, f"b{n}", "v1", (10 + 50 * n, 10, 40 + 50 * n, 40), source_type="model", review_status=status)

        _process(scene, ["v1"])

        assert len(scene.inference.calls[0].boxes) == len(statuses)

    def test_an_image_without_a_box_is_skipped_without_a_call(self, scene: _Scene) -> None:
        """SAM 2 answers a call without a box with a mask nobody asked for: none is made."""
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)

        _, outcome = _process(scene, ["v1", "v2"])

        assert [request.image for request in scene.inference.calls] == [f"{INFERENCE_MEDIA_ROOT}/a.png"]
        assert (outcome.produced, outcome.skipped, outcome.quarantined) == (1, 1, [])

    def test_a_box_reduced_to_nothing_in_pixels_is_not_sent(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        _box(dataset, "b1", "v1", (210, 10, 250, 50), in_pixels=True)

        _, outcome = _process(scene, ["v1"])

        assert scene.inference.calls == []
        assert outcome.skipped == 1

    @pytest.mark.parametrize(
        ("source_type", "review_status"),
        [("human", ""), ("model", "accepted")],
    )
    def test_an_object_a_person_outlined_is_not_asked_about(
        self, scene: _Scene, source_type: str, review_status: str
    ) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        _box(dataset, "b2", "v1", DOG_PX, "dog")
        model = SMALL if source_type == "model" else None
        _person_masks(
            dataset, "m1", "v1", car, CAR_PX, source_type=source_type, review_status=review_status, model=model
        )

        _process(scene, ["v1"])

        assert [request.boxes for request in scene.inference.calls] == [[list(DOG_PX)]]

    def test_an_image_whose_every_object_a_person_outlined_is_skipped_without_a_call(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        _person_masks(dataset, "m1", "v1", car, CAR_PX)

        _, outcome = _process(scene, ["v1"])

        assert scene.inference.calls == []
        assert outcome.skipped == 1

    def test_another_models_pending_mask_holds_nothing_back(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        _person_masks(dataset, "m1", "v1", car, CAR_PX, source_type="model", review_status="pending", model=SMALL)

        _process(scene, ["v1"])

        assert len(scene.inference.calls) == 1


class TestOutcomes:
    @pytest.fixture
    def two_cars(self, scene: _Scene) -> _Scene:
        dataset = scene.as_a_person()
        _box(dataset, "b1", "v1", CAR_PX)
        _box(dataset, "b2", "v1", DOG_PX, "dog")
        _box(dataset, "b3", "v2", CAR_PX)
        return scene

    def _answering(self, scene: _Scene, image: str, change: Callable[[list[list[Any]]], list[list[Any]]]) -> None:
        scene.inference.answer = lambda request, masks: change(masks) if request.image.endswith(image) else masks

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            (lambda masks: masks[:1], WRONG_MASK_COUNT),
            (lambda masks: [per_box * 3 for per_box in masks], WRONG_MASK_COUNT),
            (lambda masks: [[_rectangle(list(CAR_PX), HEIGHT, WIDTH)] for _ in masks], MASK_SIZE_DIFFERS),
            (
                lambda masks: [[SimpleNamespace(size=[HEIGHT, WIDTH], counts=b"0")] for _ in masks],
                UNREADABLE_MASK,
            ),
            (
                lambda masks: [[SimpleNamespace(size=[HEIGHT, WIDTH], counts=[0, HEIGHT * WIDTH])] for _ in masks],
                UNREADABLE_MASK,
            ),
        ],
        ids=[
            "fewer masks",
            "three per box",
            "height and width swapped",
            "runs short of the grid",
            "runs uncompressed",
        ],
    )
    def test_an_answer_that_does_not_fit_the_image_quarantines_it_alone(
        self, two_cars: _Scene, change: Any, reason: str
    ) -> None:
        """Written, a mask on another grid is drawn out of place, and runs that do not fill their
        grid hang pycocotools; a count that differs leaves no telling which mask is whose."""
        self._answering(two_cars, "a.png", change)

        result, outcome = _process(two_cars, ["v1", "v2"])

        assert [(item.item_id, item.reason, item.detail["record_id"]) for item in outcome.quarantined] == [
            ("v1", reason, "r1")
        ]
        assert [medium["view_id"] for medium in result["media"]] == ["v2"]

    def test_an_empty_mask_is_not_written(self, two_cars: _Scene) -> None:
        """It outlines nothing: there is nothing to review. The image is produced all the same."""
        empty = _rectangle([0, 0, 0, 0], WIDTH, HEIGHT)
        self._answering(two_cars, "a.png", lambda masks: [[empty], masks[1]])

        result, outcome = _process(two_cars, ["v1"])

        assert outcome.produced == 1
        assert [mask["box_id"] for mask in result["media"][0]["masks"]] == ["b2"]

    def test_an_image_whose_size_cannot_be_known_is_quarantined_without_a_call(
        self, two_cars: _Scene, tmp_path: Path
    ) -> None:
        """Its boxes could not be placed in pixels: they are stored relative to its size."""
        dataset = two_cars.as_a_person()
        (view,) = dataset.get_data("images", ids=["v1"])
        Path(view.uri).write_bytes(b"not an image")
        dataset.update_data("images", [view.model_copy(update={"width": 0, "height": 0})])

        _, outcome = _process(two_cars, ["v1", "v2"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("v1", IMAGE_SIZE_UNKNOWN)]
        assert len(two_cars.inference.calls) == 1

    def test_a_size_the_dataset_does_not_record_is_read_from_the_image(self, two_cars: _Scene) -> None:
        dataset = two_cars.as_a_person()
        (view,) = dataset.get_data("images", ids=["v1"])
        dataset.update_data("images", [view.model_copy(update={"width": 0, "height": 0})])

        _, outcome = _process(two_cars, ["v1"])

        assert outcome.produced == 1
        assert two_cars.inference.calls[0].boxes == [list(CAR_PX), list(DOG_PX)]

    def test_a_missing_image_is_quarantined(self, two_cars: _Scene) -> None:
        result, outcome = _process(two_cars, ["gone", "v2"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("gone", "media not found")]
        assert outcome.produced == 1

    def test_an_image_the_server_refuses_costs_only_itself(self, two_cars: _Scene) -> None:
        two_cars.inference.bad = {f"{INFERENCE_MEDIA_ROOT}/a.png"}

        _, outcome = _process(two_cars, ["v1", "v2"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [
            ("v1", "refused by the inference server")
        ]
        assert outcome.produced == 1

    @pytest.mark.parametrize("status", [0, 503])
    def test_a_server_that_does_not_answer_makes_the_chunk_transient(self, two_cars: _Scene, status: int) -> None:
        two_cars.inference.status_for_everything = status

        with pytest.raises(TransientError):
            _process(two_cars, ["v1", "v2"])

        assert two_cars.inference.closed == two_cars.inference.opened

    def test_a_request_that_can_never_pass_fails_the_chunk(self, two_cars: _Scene) -> None:
        two_cars.inference.status_for_everything = 404

        with pytest.raises(PixanoInferenceError):
            _process(two_cars, ["v1"])

    def test_an_answer_the_worker_cannot_read_fails_the_chunk(self, two_cars: _Scene) -> None:
        """What the client raises for a successful answer that does not match its schema — a client
        and a server of different versions: no medium is at fault, so none goes to quarantine."""
        two_cars.inference.status_for_everything = 200
        two_cars.inference.code_for_everything = "invalid_response"

        with pytest.raises(PixanoInferenceError, match="invalid_response"):
            _process(two_cars, ["v1", "v2"])

        assert len(two_cars.inference.calls) == 1, "no witness, no second image: the contract fails them all"

    def test_the_witness_carries_a_box_inside_the_witness_image(self, two_cars: _Scene) -> None:
        """Every image refused: the witness tells the server's fault apart, and the segmentation
        endpoint needs a box to answer anything."""
        two_cars.inference.status_for_everything = 500

        with pytest.raises(TransientError, match="witness"):
            _process(two_cars, ["v1"])

        witness = two_cars.inference.calls[-1]
        assert witness.image == witness_image()
        assert witness.boxes == [WITNESS_PROMPT]
        assert all(0 <= value <= 16 for value in WITNESS_PROMPT)

    def test_the_outcome_accounts_for_every_image(self, two_cars: _Scene) -> None:
        """Answered, refused, out of reach, without a box, gone: each image counted once."""
        dataset = two_cars.as_a_person()
        dataset.add_records({"records": [Record(id="r3"), Record(id="r4")]})
        # Outside the media root and not embedded: this worker cannot reach it.
        unreachable = Image(id="v3", record_id="r3", logical_name="image", uri="/elsewhere/c.png")
        boxless = Image(
            id="v4",
            record_id="r4",
            logical_name="image",
            uri=f"{two_cars.media.media_root}/d.png",
            width=WIDTH,
            height=HEIGHT,
        )
        dataset.add_data("images", [unreachable, boxless], raise_or_warn="none")
        two_cars.inference.bad = {f"{INFERENCE_MEDIA_ROOT}/b.png"}
        views = ["v1", "v2", "v3", "v4", "gone"]

        _, outcome = _process(two_cars, views)

        assert outcome.total == len(views)
        assert (outcome.produced, outcome.skipped) == (1, 1)
        assert sorted((item.item_id, item.reason) for item in outcome.quarantined) == [
            ("gone", "media not found"),
            ("v2", "refused by the inference server"),
            ("v3", "media not found"),
        ]

    def test_the_client_is_closed_with_the_chunk(self, two_cars: _Scene) -> None:
        _process(two_cars, ["v1", "v2"])

        assert two_cars.inference.opened == two_cars.inference.closed == 1


class TestAgainstRealLance:
    """What a segmentation writes, through the runner's reader and writer."""

    def test_masks_arrive_pending_on_the_objects_of_their_boxes(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        dog = _box(dataset, "b2", "v1", DOG_PX, "dog", source_type="model", review_status="pending")

        (outcome,) = _run(scene)

        assert (outcome.produced, outcome.skipped) == (1, 1)
        masks = {mask.entity_id: mask for mask in _masks(scene)}
        assert set(masks) == {car, dog}
        for entity_id, corners in ((car, CAR_PX), (dog, DOG_PX)):
            mask = masks[entity_id]
            assert (mask.view_id, mask.record_id, mask.size) == ("v1", "r1", [HEIGHT, WIDTH])
            assert isinstance(mask.counts, bytes)
            assert _bounds(mask) == list(corners)
            assert (mask.source_type, mask.source_name, mask.review_status) == ("model", "segmentation", "pending")
            metadata = json.loads(mask.source_metadata)
            assert (metadata["kind"], metadata["model"], metadata["model_version"]) == (
                "segmentation",
                TINY,
                CHECKPOINTS[TINY],
            )
            assert metadata["params"] == {"model": TINY, "media": ["image"], "overlap_threshold": 0.5}

    def test_the_dataset_gains_its_masks_table_as_the_application_sees_it(self, scene: _Scene) -> None:
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)
        assert json.loads((scene.path / "info.json").read_text())["mask"] is None

        _run(scene)

        opened = scene.as_a_person()
        assert opened.info.mask is not None and issubclass(opened.info.mask, CompressedRLE)
        assert json.loads((scene.path / "info.json").read_text())["mask"] is not None
        assert len(opened.get_data("masks", limit=None)) == 1

    def test_a_rerun_doubles_nothing_and_keeps_the_identifiers(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        _box(dataset, "b1", "v1", CAR_PX)
        _box(dataset, "b2", "v1", DOG_PX, "dog")
        _run(scene)
        first = sorted((mask.id, mask.entity_id, mask.counts) for mask in _masks(scene))

        _run(scene, "job-2")

        assert sorted((mask.id, mask.entity_id, mask.counts) for mask in _masks(scene)) == first

    def test_a_second_model_adds_one_mask_per_object(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        dog = _box(dataset, "b2", "v1", DOG_PX, "dog")
        _run(scene)

        _run(scene, "job-2", model=SMALL)

        assert _summary(scene) == [
            (car, SMALL, "pending", "model"),
            (car, TINY, "pending", "model"),
            (dog, SMALL, "pending", "model"),
            (dog, TINY, "pending", "model"),
        ]

    @pytest.mark.parametrize(
        ("source_type", "review_status"),
        [("human", ""), ("model", "accepted")],
    )
    def test_an_object_a_person_outlined_gets_no_mask_from_any_model(
        self, scene: _Scene, source_type: str, review_status: str
    ) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        model = TINY if source_type == "model" else None
        _person_masks(
            dataset, "m1", "v1", car, CAR_PX, source_type=source_type, review_status=review_status, model=model
        )
        before = Dataset(scene.path).get_data("masks", ids=["m1"])[0].model_dump(exclude={"created_at", "updated_at"})

        _run(scene)
        _run(scene, "job-2", model=SMALL)

        assert [mask.id for mask in _masks(scene)] == ["m1"]
        assert _masks(scene)[0].model_dump(exclude={"created_at", "updated_at"}) == before

    @pytest.mark.parametrize(
        ("persons_class", "written"),
        [("car", False), ("", False), ("CAR", False), ("dog", True)],
        ids=["same class", "no class stands for any", "class case aside", "another class"],
    )
    def test_a_persons_mask_on_another_object_holds_back_a_mask_of_its_class(
        self, scene: _Scene, persons_class: str, written: bool
    ) -> None:
        """A person outlined the car without drawing its box; the model's car over it would say
        again what they said."""
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        dataset.add_data("entities", [_entity(dataset, id="outlined", record_id="r1", category=persons_class)])
        _person_masks(dataset, "m1", "v1", "outlined", CAR_PX)

        _run(scene)

        assert (car in {mask.entity_id for mask in _masks(scene)}) is written

    def test_below_the_threshold_it_is_written(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        dataset.add_data("entities", [_entity(dataset, id="outlined", record_id="r1", category="car")])
        # The person's outline covers the box's left half: an overlap of one half.
        _person_masks(dataset, "m1", "v1", "outlined", (20, 10, 40, 50))

        _run(scene, overlap_threshold=0.6)

        assert car in {mask.entity_id for mask in _masks(scene)}

    @pytest.mark.parametrize("change", ["moved", "deleted", "reassigned", "object deleted"])
    def test_a_box_changed_while_the_model_ran_gets_no_mask(self, scene: _Scene, change: str) -> None:
        """`process` runs outside the write lock. A detection rerun in this worker meanwhile, or a
        delete, leaves the answer about a box that no longer says the same."""
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        dog = _box(dataset, "b2", "v1", DOG_PX, "dog", source_type="model", review_status="pending")
        params = _params(scene)
        (chunk,) = list(scene.kind.plan(scene.reader(fresh=True), params))
        scene.kind.prepare(scene.writer(params), params)
        result = scene.kind.process(scene.reader(), chunk.payload, params)

        worker = scene.as_the_worker()
        (box,) = worker.get_data("bboxes", ids=["b2"])
        if change == "moved":
            worker.update_data("bboxes", [box.model_copy(update={"coords": [0.0, 0.0, 0.2, 0.2]})])
        elif change == "deleted":
            worker.delete_data("bboxes", ["b2"])
        elif change == "reassigned":
            worker.add_data("entities", [_entity(worker, id="other", record_id="r1", category="cat")])
            worker.update_data("bboxes", [box.model_copy(update={"entity_id": "other"})])
        else:
            worker.delete_data("entities", [dog])
        scene.kind.write(scene.writer(params), result, chunk.payload, params)

        assert [mask.entity_id for mask in _masks(scene)] == [car]

    def test_an_object_outlined_while_the_model_ran_gets_no_mask(self, scene: _Scene) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX)
        params = _params(scene)
        (chunk,) = list(scene.kind.plan(scene.reader(fresh=True), params))
        scene.kind.prepare(scene.writer(params), params)
        result = scene.kind.process(scene.reader(), chunk.payload, params)

        # The person outlined only part of the car: by the overlap alone, the model's would pass.
        _person_masks(scene.as_the_worker(), "m1", "v1", car, CAR_CORNER_PX)
        scene.kind.write(scene.writer(params), result, chunk.payload, params)

        assert [mask.id for mask in _masks(scene)] == ["m1"]

    def test_an_image_whose_only_box_was_deleted_loses_its_pending_mask(self, scene: _Scene) -> None:
        """A reject is the box's delete. Its image is skipped on the rerun — nothing left to ask —
        and replaced with no mask: left, the mask would outline what the person said is not there."""
        car = _box(scene.as_a_person(), "b1", "v1", CAR_PX, source_type="model", review_status="pending")
        _box(scene.as_a_person(), "b2", "v2", CAR_PX)
        _run(scene)
        assert car in {mask.entity_id for mask in _masks(scene)}
        scene.as_a_person().delete_data("bboxes", ["b1"])

        (outcome,) = _run(scene, "job-2")

        assert outcome.skipped == 1
        assert [mask.entity_id for mask in _masks(scene)] == ["e-b2"]

    def test_a_worker_whose_dataset_predates_the_table_writes_into_it(self, scene: _Scene) -> None:
        """Planning and preparation ran in one worker; the chunk runs in another, which opened the
        dataset before the table existed and still holds its metadata without it."""
        _box(scene.as_a_person(), "b1", "v1", CAR_PX)
        opened_before = Dataset(scene.path)
        params = _params(scene)
        (chunk,) = list(scene.kind.plan(scene.reader(fresh=True), params))
        scene.kind.prepare(scene.writer(params), params)
        runner._open_datasets[(scene.library, DATASET_ID)] = opened_before
        assert "masks" not in opened_before.info.tables

        result = scene.kind.process(scene.reader(), chunk.payload, params)
        scene.kind.write(scene.writer(params), result, chunk.payload, params)

        assert [mask.entity_id for mask in _masks(scene)] == ["e-b1"]

    def test_preparing_gives_the_dataset_its_masks_table_once(self, scene: _Scene) -> None:
        params = _params(scene)

        scene.kind.prepare(scene.writer(params), params)
        info = (scene.path / "info.json").read_text()
        scene.kind.prepare(scene.writer(params), params)

        assert "masks" in Dataset(scene.path).info.tables
        assert (scene.path / "info.json").read_text() == info

    def test_replacing_the_previous_masks_clears_the_pending_ones_of_every_model_and_nothing_else(
        self, scene: _Scene
    ) -> None:
        dataset = scene.as_a_person()
        car = _box(dataset, "b1", "v1", CAR_PX, source_type="model", review_status="pending")
        _box(dataset, "b2", "v1", DOG_PX, "dog")
        _run(scene)
        _run(scene, "job-2", model=SMALL)
        person = scene.as_a_person()
        (accepted,) = [
            mask for mask in person.get_data("masks", limit=None) if mask.entity_id == car and _model_of(mask) == TINY
        ]
        person.update_data("masks", [accepted.model_copy(update={"review_status": "accepted"})])
        boxes = sorted(box.model_dump_json() for box in Dataset(scene.path).get_data("bboxes", limit=None))
        entities = sorted(entity.model_dump_json() for entity in Dataset(scene.path).get_data("entities", limit=None))
        params = _params(scene, replace_previous=True)

        scene.plan(params, "job-3")

        assert [(mask.id, mask.review_status) for mask in _masks(scene)] == [(accepted.id, "accepted")]
        assert sorted(box.model_dump_json() for box in Dataset(scene.path).get_data("bboxes", limit=None)) == boxes
        assert (
            sorted(entity.model_dump_json() for entity in Dataset(scene.path).get_data("entities", limit=None))
            == entities
        )


# What the real server answered, captured on 2026-10-08 from upstream pixano-inference: its
# /v1/inference/segmentation route, unmodified, over Sam2ImageModel serving sam2.1-hiera-tiny on CPU
# (float32, no compile, as docker/inference/models.cpu.py serves it), called through FastAPI's test
# client on an 80 × 60 image holding a red rectangle and a blue disc. One box, then three: the
# rectangle, the disc, and the whole image. The masks nest per box, then per output; the scores
# are a base64 array of shape [boxes, 1]; the runs are compressed strings.
CAPTURED_SIZE = (80, 60)
CAPTURED_BOXES = [[8, 10, 36, 46], [45, 15, 73, 51], [0, 0, 80, 60]]
ONE_BOX_BODY = (
    '{"id":"ray-sam2.1-tiny-51b3062479f5","status":"SUCCESS","timestamp":"2026-10-08T20:45:22.535447Z",'
    '"processingTime":1.7910442352294922,"metadata":{"model_class":"Sam2ImageModel",'
    '"model_path":"facebook/sam2.1-hiera-tiny"},"data":{"masks":[[{"size":[60,80],'
    '"counts":"Z?T1h000000000000000000000000000000000000000000000000000000Vb2"}]],'
    '"scores":{"shape":[1,1],"dtype":"float32","data":"eZF7Pw=="},"imageEmbedding":null,'
    '"highResolutionFeatures":null,"maskLogits":null}}'
)
THREE_BOXES_BODY = (
    '{"id":"ray-sam2.1-tiny-a00471e4ec8e","status":"SUCCESS","timestamp":"2026-10-08T20:45:24.281162Z",'
    '"processingTime":1.7434730529785156,"metadata":{"model_class":"Sam2ImageModel",'
    '"model_path":"facebook/sam2.1-hiera-tiny"},"data":{"masks":[[{"size":[60,80],'
    '"counts":"Z?T1h000000000000000000000000000000000000000000000000000000Vb2"}],[{"size":[60,80],'
    '"counts":"Xe2:_16K4L4M2N2N2N2O0O2O0O2O0000000001N101N101N2N2N2N3L4L5J[<"}],[{"size":[60,80],'
    '"counts":"0Z?T1^A000EmNMS1>0000000EmNMS1>0000000000000000000000000000000000001]a0UOZ_O6K5K3N2N2N2N2O0O2O0O'
    '2O0000000@mN7S1:N101N10^OQO8m0=N2N2N3MYO\\\\O:?e0LY:EWF0TN"}]],"scores":{"shape":[3,1],"dtype":"float32",'
    '"data":"eZF7P1F9fD/LuHg/"},"imageEmbedding":null,"highResolutionFeatures":null,"maskLogits":null}}'
)
# Asked about no box at all, SAM 2 answers one mask nobody asked for — not an error.
NO_BOX_BODY = (
    '{"id":"ray-sam2.1-tiny-3b27dd7996c3","status":"SUCCESS","timestamp":"2026-10-08T20:45:25.859146Z",'
    '"processingTime":1.5751721858978271,"metadata":{"model_class":"Sam2ImageModel",'
    '"model_path":"facebook/sam2.1-hiera-tiny"},"data":{"masks":[[{"size":[60,80],'
    '"counts":"Z?T1h0LYOSOg0Q100000IYOUO0Oi0o024L00O1IYOXOh0P1N000000HZOXOh0P1N000000HYOXOj0m0VOQOg0k0YOWO0Mg0'
    'S10HYOWO2Ne0=ZONn03QOL1Gk0Q1Za0POk]O1_1:J5L5L2N2N2N10FYO\\\\OK2j0o0OEWOCh0j0O00000000O2O0O2O001N2N2N2N3L4L5J[<"'
    '}]],"scores":{"shape":[1,1],"dtype":"float32","data":"tmAzMg=="},"imageEmbedding":null,'
    '"highResolutionFeatures":null,"maskLogits":null}}'
)
# What each captured mask paints, as pycocotools decodes it: the pixel corners of its bounds.
CAPTURED_BOUNDS = [[8, 10, 36, 46], [45, 15, 73, 51], [0, 0, 80, 60]]


class _Server:
    """The inference at its HTTP edge: the real client sends its request, and gets these bodies."""

    def __init__(self, segmentation_body: str) -> None:
        self.body = segmentation_body
        self.requests: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json=[
                    {"name": TINY, "capability": "segmentation", "modelPath": CHECKPOINTS[TINY], "status": "RUNNING"}
                ],
            )
        assert request.url.path == "/v1/inference/segmentation", request.url.path
        self.requests.append(json.loads(request.content))
        return httpx.Response(200, content=self.body.encode(), headers={"content-type": "application/json"})


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[_Scene, Callable[[str], _Server]]:
    """The captured image's dataset, its boxes drawn where the capture prompted, and a way to serve a body."""
    library, media_root = _make_scene(tmp_path, monkeypatch, {"v1": ("r1", "shapes.png", CAPTURED_SIZE)})
    dataset = Dataset(library / DATASET_ID)
    # In pixels, as the capture prompted them: the kind sends them back unchanged.
    for n, corners in enumerate(CAPTURED_BOXES):
        dataset.add_data("entities", [_entity(dataset, id=f"e{n}", record_id="r1", **{CLASS_FIELD: f"shape {n}"})])
        dataset.add_data(
            "bboxes",
            [
                BBox(
                    id=f"b{n}",
                    record_id="r1",
                    view_id="v1",
                    entity_id=f"e{n}",
                    coords=[float(value) for value in corners],
                    format="xyxy",
                    is_normalized=False,
                    source_type="human",
                )
            ],
        )

    def serve(body: str) -> _Server:
        server = _Server(body)
        transport = httpx.MockTransport(server.handle)
        monkeypatch.setattr(
            "pixano_worker.kinds.inference.SyncPixanoInferenceClient",
            lambda url, **kwargs: SyncPixanoInferenceClient(url, transport=transport, **kwargs),
        )
        return server

    media = MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT)
    return _Scene(library, media, None, SegmentationKind("http://inference")), serve  # type: ignore[arg-type]


class TestWhatTheServerAnswers:
    """Bodies the real server returned, through the real client, to the kind."""

    def test_the_request_on_the_wire_asks_one_mask_per_box_on_a_fresh_image(self, served: Any) -> None:
        scene, serve = served
        server = serve(THREE_BOXES_BODY)

        _run(scene)

        (sent,) = server.requests
        assert sent["boxes"] == CAPTURED_BOXES
        assert (sent["multimaskOutput"], sent["numMultimaskOutputs"], sent["resetPredictor"]) == (False, 1, True)
        assert sent["image"] == f"{INFERENCE_MEDIA_ROOT}/shapes.png"

    def test_each_mask_of_the_answer_lands_on_the_object_of_its_box(self, served: Any) -> None:
        scene, serve = served
        serve(THREE_BOXES_BODY)

        (outcome,) = _run(scene)

        assert outcome.produced == 1
        masks = {mask.entity_id: mask for mask in _masks(scene)}
        width, height = CAPTURED_SIZE
        assert {entity_id: (mask.size, _bounds(mask)) for entity_id, mask in masks.items()} == {
            f"e{n}": ([height, width], bounds) for n, bounds in enumerate(CAPTURED_BOUNDS)
        }
        assert all(isinstance(mask.counts, bytes) for mask in masks.values())

    def test_an_answer_of_one_mask_for_three_boxes_quarantines_the_image(self, served: Any) -> None:
        """What a server that lost the boxes would answer: SAM's mask for no box at all."""
        scene, serve = served
        serve(NO_BOX_BODY)

        (outcome,) = _run(scene)

        assert [(item.item_id, item.reason, item.detail["masks"]) for item in outcome.quarantined] == [
            ("v1", WRONG_MASK_COUNT, [1])
        ]
        assert _masks(scene) == []

    def test_numeric_runs_are_compressed_by_the_client_before_the_kind_sees_them(self, served: Any) -> None:
        """The client's model accepts uncompressed runs too, and compresses them on parsing.
        Pixano's mask schema takes compressed bytes only, so the kind relies on that — and refuses
        any other shape reaching it (see `TestOutcomes`)."""
        scene, serve = served
        body = json.loads(ONE_BOX_BODY)
        compressed = body["data"]["masks"][0][0]
        pixels = mask_api.decode({"size": compressed["size"], "counts": compressed["counts"].encode()})
        compressed["counts"] = _uncompressed_runs(pixels)
        body["data"]["masks"] = [[dict(compressed)] for _ in CAPTURED_BOXES]
        body["data"]["scores"] = {"shape": [3, 1], "dtype": "float32", "data": "eZF7P1F9fD/LuHg/"}
        serve(json.dumps(body))

        (outcome,) = _run(scene)

        assert outcome.produced == 1
        (first, *_) = sorted(_masks(scene), key=lambda mask: mask.entity_id)
        assert isinstance(first.counts, bytes)
        assert (mask_api.decode({"size": first.size, "counts": first.counts}) == pixels).all()

    def test_the_scores_parse_though_no_column_keeps_them(self, served: Any) -> None:
        """SAM's predicted overlap per mask, an array the client decodes; the mask schema has no
        score column, so it is not written (backend-processing §18), and nothing stands in for it."""
        from pixano_inference.schemas import SegmentationResponse

        parsed = SegmentationResponse.model_validate_json(THREE_BOXES_BODY)

        assert parsed.data.scores.to_numpy().shape == (3, 1)
        assert [len(per_box) for per_box in parsed.data.masks] == [1, 1, 1]
        assert "confidence" not in CompressedRLE.model_fields


def _uncompressed_runs(pixels: np.ndarray) -> list[int]:
    """A mask's runs, column by column, background first, as COCO writes them uncompressed."""
    flat = pixels.flatten(order="F")
    runs, current, length = [], 0, 0
    for value in flat:
        if value == current:
            length += 1
        else:
            runs.append(length)
            current, length = value, 1
    runs.append(length)
    return [int(run) for run in runs]
