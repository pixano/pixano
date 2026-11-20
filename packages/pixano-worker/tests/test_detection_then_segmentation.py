# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A detection, then a segmentation of its boxes, on a dataset that had no masks; a person
reviews; both run again, and the review stands.

Each side runs its own code. The jobs run as the worker's runner composes them, without the
queue: planned on the dataset reopened for the job, then prepared, then each chunk processed and
written through the runner's own reader and writer. The person reviews through pixano's annotation
service, on an instance opened the way the application opens one, with the bodies the interfaces
send. Only the inference server is a stand-in, and only at its HTTP edge: the worker's real client
sends its requests and parses the answers, shaped as the real server shapes them.
"""

import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pytest
from PIL import Image as PILImage
from pixano_inference.client import SyncPixanoInferenceClient
from pixano_inference.schemas import NDArrayFloat
from pixano_worker import runner
from pixano_worker.kinds import DetectionKind, JobKind, SegmentationKind
from pixano_worker.media import MediaResolver
from pycocotools import mask as mask_api

from pixano.api.models import BBoxUpdate, EntityCreate, EntityUpdate, MaskUpdate
from pixano.api.resources import BBOX_RESOURCE, ENTITY_RESOURCE, MASK_RESOURCE
from pixano.api.service import BaseService
from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record, label_field_of


DATASET_ID = "shapes"
RECORD_ID = "r1"
VIEW_ID = "v1"
# Not square: a mask whose height and width were swapped, or read row by row, would land elsewhere.
WIDTH, HEIGHT = 200, 120
IMAGE_FILE = f"{VIEW_ID}.png"
# The same media storage, mounted elsewhere by the inference: the worker sends it this path.
INFERENCE_MEDIA_ROOT = "/inference-media"

# What the inference serves: one detector and two segmentation models, with their checkpoints.
DETECTOR, TINY, SMALL = "yolo26n", "sam2.1-tiny", "sam2.1-small"
SERVED = {
    DETECTOR: ("detection", "YOLOModel", "yolo26n.pt"),
    TINY: ("segmentation", "Sam2ImageModel", "facebook/sam2.1-hiera-tiny"),
    SMALL: ("segmentation", "Sam2ImageModel", "facebook/sam2.1-hiera-small"),
}

# What the detector finds on the image at every run: pixel corners, score and class. The key names
# what the person then does with the object. The boxes do not overlap and their classes differ, so
# what happens to one says nothing about another.
DETECTIONS: dict[str, tuple[list[int], float, str]] = {
    "mask accepted": ([10, 10, 40, 50], 0.91, "car"),
    "mask moved": ([50, 10, 80, 50], 0.82, "bus"),
    "mask rejected": ([90, 10, 120, 50], 0.73, "dog"),
    "class changed": ([130, 10, 160, 50], 0.64, "person"),
    "box rejected": ([170, 10, 195, 50], 0.55, "horse"),
    "untouched": ([10, 60, 60, 110], 0.52, "cat"),
}
# Each segmentation model outlines a box a little differently: the small one leaves a pixel's
# border, so that its masks are not the tiny one's.
INSET_PX = {TINY: 0, SMALL: 1}

# The person drags a mask a few pixels to the right.
MOVE_PX = 4
# The class a person gives an object instead of the detector's.
NEW_CLASS = "truck"
NEW_ENTITY_ID = "e-truck"

# The annotation interface (ui/apps/web) sends an Accept as the status alone, or riding on the edit,
# and a Reject as the row's delete with `prune_orphan_entity` (payloadBuilders.ts). It sends an edit
# as the whole row, with its own provenance (maskPayloadBuilder.ts, `buildMaskUpdate`;
# bboxPayloadBuilder.ts, `buildBBoxUpdate`).
WEB_SOURCE = {"source_type": "other", "source_name": "Pixano", "source_metadata": "{}"}
WEB_CONFIDENCE = 1

# The server stamps these on every write. They say when a row was written, not what it holds.
SERVER_STAMPS = frozenset({"created_at", "updated_at"})


def _rle(corners: list[int], inset: int = 0) -> dict[str, Any]:
    """A mask filling a box, less an inset, on the image's grid, as pycocotools compresses it."""
    left, top, right, bottom = corners
    pixels = np.zeros((HEIGHT, WIDTH), dtype=np.uint8, order="F")
    pixels[top + inset : bottom - inset, left + inset : right - inset] = 1
    encoded = mask_api.encode(pixels)
    return {"size": list(encoded["size"]), "counts": encoded["counts"].decode()}


class _Inference:
    """The inference server at its HTTP edge, answering as the real one does.

    The detector finds `DETECTIONS` on the image. A segmentation model answers, for each box, one
    mask filling it; asked for several masks per box, three, as SAM 2 does — and an error for any
    other count, or for an empty list of boxes.
    """

    def __init__(self, image: str) -> None:
        self.image = image
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json=[
                    {"name": name, "capability": capability, "modelClass": cls, "modelPath": path, "status": "RUNNING"}
                    for name, (capability, cls, path) in SERVED.items()
                ],
            )
        body = json.loads(request.content)
        self.requests.append((request.url.path, body))
        if request.url.path == "/v1/inference/detection":
            found = list(DETECTIONS.values()) if body["image"] == self.image else []
            return self._answer(
                body,
                {
                    "boxes": [corners for corners, _, _ in found],
                    "scores": [score for _, score, _ in found],
                    "classes": [name for _, _, name in found],
                    "masks": None,
                },
            )
        if request.url.path == "/v1/inference/segmentation":
            per_box = 3 if body.get("multimaskOutput", True) else 1
            if (
                body["image"] != self.image
                or body.get("boxes") == []
                or (per_box == 3) != (body.get("numMultimaskOutputs", 3) == 3)
            ):
                return httpx.Response(500, json={"detail": "Inference error."})
            boxes = body["boxes"]
            masks = [[_rle(box, INSET_PX[body["model"]])] * per_box for box in boxes]
            scores = NDArrayFloat.from_numpy(np.full((len(boxes), per_box), 0.9, dtype=np.float32))
            return self._answer(
                body,
                {
                    "masks": masks,
                    "scores": scores.model_dump(),
                    "imageEmbedding": None,
                    "highResolutionFeatures": None,
                    "maskLogits": None,
                },
            )
        return httpx.Response(404, json={"detail": "Not Found"})

    @staticmethod
    def _answer(body: dict[str, Any], data: dict[str, Any]) -> httpx.Response:
        """The envelope the server wraps every answer in (api/v1/helpers.py, `run_inference`)."""
        capability, cls, path = SERVED[body["model"]]
        return httpx.Response(
            200,
            json={
                "id": f"ray-{body['model']}-0",
                "status": "SUCCESS",
                "timestamp": "2026-10-08T00:00:00Z",
                "processingTime": 0.1,
                "metadata": {"model_class": cls, "model_path": path},
                "data": data,
            },
        )


@dataclass
class _Deployment:
    """The library the worker and the application share, how the worker designates its media, the
    inference, and the worker's two kinds."""

    library: Path
    media: MediaResolver
    inference: _Inference
    detection: DetectionKind
    segmentation: SegmentationKind

    @property
    def path(self) -> Path:
        return self.library / DATASET_ID


@pytest.fixture
def deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Deployment:
    """A library holding one dataset: one record, one image on disk, tables for boxes and objects
    — and none for masks, as a dataset imported with boxes only."""
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay
    # independent of each other.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    PILImage.new("RGB", (WIDTH, HEIGHT)).save(media_root / IMAGE_FILE)
    library = tmp_path / "library"
    created = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Shapes", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )
    created.add_records({"records": [Record(id=RECORD_ID)]})
    created.add_data(
        "images",
        [
            Image(
                id=VIEW_ID,
                record_id=RECORD_ID,
                logical_name="image",
                uri=str(media_root / IMAGE_FILE),
                width=WIDTH,
                height=HEIGHT,
            )
        ],
        raise_or_warn="none",
    )

    inference = _Inference(f"{INFERENCE_MEDIA_ROOT}/{IMAGE_FILE}")
    transport = httpx.MockTransport(inference.handle)
    monkeypatch.setattr(
        "pixano_worker.kinds.inference.SyncPixanoInferenceClient",
        lambda url, **kwargs: SyncPixanoInferenceClient(url, transport=transport, **kwargs),
    )
    return _Deployment(
        library=library,
        media=MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT),
        inference=inference,
        detection=DetectionKind("http://inference", ""),
        segmentation=SegmentationKind("http://inference", ""),
    )


def _run(deployment: _Deployment, kind: JobKind, job_id: str, **params: Any) -> list[Any]:
    """Run one job as the runner runs it, without the queue.

    Planning is the runner's own (`_plan_and_prepare`): the job split on the dataset reopened,
    bypassing the worker's cache, then `prepare` under the dataset's write lock. Then each chunk is
    processed and written through the runner's own reader and writer, which serve that reopened
    dataset from the cache.

    Returns:
        Each chunk's outcome.
    """
    checked = kind.validate_params(params)
    chunks = runner._plan_and_prepare(
        kind, deployment.library, DATASET_ID, deployment.media, job_id, checked, threading.Event()
    )
    outcomes = []
    for chunk in chunks:
        result = kind.process(
            runner._reader_for(deployment.library, DATASET_ID, deployment.media), chunk.payload, checked
        )
        outcomes.append(kind.outcome(result, chunk.payload, chunk.task_count))
        kind.write(
            runner._writer_for(deployment.library, DATASET_ID, kind, job_id, checked), result, chunk.payload, checked
        )
    return outcomes


def _detect(deployment: _Deployment, job_id: str, **params: Any) -> None:
    (outcome,) = _run(deployment, deployment.detection, job_id, model=DETECTOR, **params)
    assert outcome.produced == 1, "the detector did not answer for the image"


def _segment(deployment: _Deployment, job_id: str, model: str, **params: Any) -> Any:
    (outcome,) = _run(deployment, deployment.segmentation, job_id, model=model, **params)
    return outcome


def _open_as_the_application(deployment: _Deployment) -> Dataset:
    """The dataset as the application opens it for a request (`get_dataset_dep`): an instance of its own."""
    return Dataset.find(DATASET_ID, deployment.library)


@dataclass(frozen=True)
class _Object:
    """An object as one reads it back: its entity and class, its boxes and its masks."""

    entity: Any
    label: str
    boxes: list[BBox]
    masks: list[CompressedRLE]

    def masks_by(self, model: str) -> list[CompressedRLE]:
        return [mask for mask in self.masks if _model_of(mask) == model]


def _model_of(row: Any) -> str:
    """The model a row's provenance names, "" for a row no model wrote."""
    return str(json.loads(row.source_metadata).get("model") or "")


def _content(row: Any) -> dict[str, Any]:
    """Everything a row holds, apart from when it was written."""
    return row.model_dump(exclude=SERVER_STAMPS)


def _objects(deployment: _Deployment) -> dict[str, _Object]:
    """Every object of the dataset with its boxes and masks, read through a newly opened instance."""
    dataset = Dataset(deployment.path)
    assert dataset.info.entity is not None
    field = label_field_of(dataset.info.entity)
    assert field is not None
    boxes = dataset.get_data("bboxes", limit=None)
    masks = dataset.get_data("masks", limit=None) if "masks" in dataset.info.tables else []
    return {
        entity.id: _Object(
            entity=entity,
            label=getattr(entity, field),
            boxes=[box for box in boxes if box.entity_id == entity.id],
            masks=[mask for mask in masks if mask.entity_id == entity.id],
        )
        for entity in dataset.get_data("entities", limit=None)
    }


def _all_masks(deployment: _Deployment) -> list[dict[str, Any]]:
    """Everything every mask of the dataset holds, by identifier."""
    masks = [_content(mask) for found in _objects(deployment).values() for mask in found.masks]
    return sorted(masks, key=lambda mask: mask["id"])


def _corners(box: BBox) -> list[int]:
    """A stored box, normalised top-left and size, as the detector's pixel corners."""
    x, y, w, h = box.coords
    return [round(x * WIDTH), round(y * HEIGHT), round((x + w) * WIDTH), round((y + h) * HEIGHT)]


def _at(objects: dict[str, _Object], role: str) -> list[_Object]:
    """The objects whose box is where the detector finds the object of this role."""
    corners = DETECTIONS[role][0]
    return [found for found in objects.values() if any(_corners(box) == corners for box in found.boxes)]


def _by_role(objects: dict[str, _Object]) -> dict[str, _Object]:
    """The first detection's objects, each under the name of what the person does with it."""
    found = {}
    for role in DETECTIONS:
        there = _at(objects, role)
        assert len(there) == 1, f"{len(there)} object(s) where the detector finds the one to be {role}"
        found[role] = there[0]
    return found


def _bounds(mask: CompressedRLE) -> list[int]:
    """The pixel corners of what a mask paints, as pycocotools decodes it."""
    x, y, w, h = mask_api.toBbox({"size": list(mask.size), "counts": mask.counts})
    return [int(x), int(y), int(x + w), int(y + h)]


def _save(dataset: Dataset, resource: Any, transport: Any, row_id: str, body: dict[str, Any]) -> None:
    """Send an update the way the interface's Save does, through the application's route.

    The interface strips the id and asks to prune an entity the edit leaves without annotations
    (api/annotations.ts, `updateAnnotation`). The route reads the body through its transport model
    and hands the fields that were set to the service (api/routers/resources.py).
    """
    patch = {key: value for key, value in body.items() if key != "id"}
    payload = transport.model_validate(patch).model_dump(exclude_unset=True)
    BaseService(dataset, resource).update(row_id, payload, prune_orphan_entity=True)


def _reject(dataset: Dataset, resource: Any, row_id: str) -> None:
    """Send a Reject the way the interface's Save does: the row's delete, asking to prune the entity
    nothing else names (api/annotations.ts, `deleteAnnotation`)."""
    BaseService(dataset, resource).delete(row_id, prune_orphan_entity=True)


def _web_mask_update(mask: CompressedRLE, counts: str, entity_id: str | None = None) -> dict[str, Any]:
    """The body `buildMaskUpdate` builds for a mask moved or given another object."""
    return {
        "id": mask.id,
        "record_id": mask.record_id,
        "entity_id": entity_id or mask.entity_id,
        "view_id": mask.view_id,
        "size": list(mask.size),
        "counts": counts,
        **WEB_SOURCE,
    }


def _web_box_update(box: BBox, entity_id: str) -> dict[str, Any]:
    """The body `buildBBoxUpdate` builds for a box given another object."""
    return {
        "id": box.id,
        "record_id": box.record_id,
        "entity_id": entity_id,
        "view_id": box.view_id,
        "coords": box.coords,
        "format": "xywh",
        "is_normalized": True,
        "confidence": WEB_CONFIDENCE,
        **WEB_SOURCE,
    }


def _create_entity(dataset: Dataset, label: str) -> None:
    """What the new interface queues before reassigning an annotation to a new object
    (buildPayloads.ts, `buildEntityCreateMutation`)."""
    assert dataset.info.entity is not None
    field = label_field_of(dataset.info.entity)
    body = {"id": NEW_ENTITY_ID, "record_id": RECORD_ID, "parent_id": "", field: label}
    BaseService(dataset, ENTITY_RESOURCE).create(EntityCreate.model_validate(body).model_dump())


def _moved(mask: CompressedRLE) -> str:
    """A mask's runs once dragged `MOVE_PX` pixels to the right, as the interface re-encodes it."""
    pixels = mask_api.decode({"size": list(mask.size), "counts": mask.counts})
    return mask_api.encode(np.asfortranarray(np.roll(pixels, MOVE_PX, axis=1)))["counts"].decode()


class TestDetectionThenSegmentation:
    """Masks on the objects a detection found, pending review, on a dataset that had no masks."""

    def test_each_box_gets_a_pending_mask_on_its_object_in_a_table_the_job_added(
        self, deployment: _Deployment
    ) -> None:
        _detect(deployment, "detect-1")
        assert json.loads((deployment.path / "info.json").read_text())["mask"] is None

        outcome = _segment(deployment, "segment-1", TINY)

        assert (outcome.produced, outcome.skipped, outcome.quarantined) == (1, 0, [])
        objects = _objects(deployment)
        assert len(objects) == len(DETECTIONS)
        for found in objects.values():
            (box,) = found.boxes
            (mask,) = found.masks
            assert (mask.view_id, mask.record_id, mask.size) == (VIEW_ID, RECORD_ID, [HEIGHT, WIDTH])
            # On the image that is not square, the mask paints exactly where its box is.
            assert _bounds(mask) == _corners(box)
            assert (mask.source_type, mask.source_name, mask.review_status) == ("model", "segmentation", "pending")
            metadata = json.loads(mask.source_metadata)
            assert (metadata["model"], metadata["model_version"]) == (TINY, SERVED[TINY][2])

    def test_the_application_sees_the_table_without_creating_it_again(self, deployment: _Deployment) -> None:
        """The application lists masks through a service that creates a missing table: it finds
        the job's, and leaves `info.json` as the job wrote it."""
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        info = deployment.path / "info.json"
        written = (info.read_text(), info.stat().st_mtime_ns)

        application = _open_as_the_application(deployment)
        table = BaseService(application, MASK_RESOURCE).resolve_table()

        assert table == "masks"
        assert len(application.get_data(table, limit=None)) == len(DETECTIONS)
        assert (info.read_text(), info.stat().st_mtime_ns) == written

    def test_the_inference_is_asked_once_for_every_box(self, deployment: _Deployment) -> None:
        _detect(deployment, "detect-1")

        _segment(deployment, "segment-1", TINY)

        ((path, sent),) = [request for request in deployment.inference.requests if "segmentation" in request[0]]
        assert sorted(sent["boxes"]) == sorted(corners for corners, _, _ in DETECTIONS.values())
        assert (sent["multimaskOutput"], sent["numMultimaskOutputs"], sent["resetPredictor"]) == (False, 1, True)

    def test_a_rerun_doubles_nothing(self, deployment: _Deployment) -> None:
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        first = _all_masks(deployment)

        _segment(deployment, "segment-2", TINY)

        rerun = _all_masks(deployment)
        assert [mask["id"] for mask in rerun] == [mask["id"] for mask in first]
        # The same rows, but for the job that wrote them.
        assert [{**mask, "source_metadata": None} for mask in rerun] == [
            {**mask, "source_metadata": None} for mask in first
        ]

    def test_a_second_model_adds_one_mask_per_object(self, deployment: _Deployment) -> None:
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)

        _segment(deployment, "segment-2", SMALL)

        for found in _objects(deployment).values():
            assert sorted(_model_of(mask) for mask in found.masks) == sorted([SMALL, TINY])
            assert _bounds(found.masks_by(SMALL)[0]) != _bounds(found.masks_by(TINY)[0])


@dataclass(frozen=True)
class _Reviewed:
    """The objects before and after a person reviewed them."""

    detected: dict[str, _Object]
    reviewed: dict[str, _Object]
    moved_counts: str


@pytest.fixture
def reviewed(deployment: _Deployment) -> _Reviewed:
    """A detection, both segmentation models, then a person's review of the tiny model's masks: one
    accepted, one moved, one rejected; one object's class changed, one box rejected, one object
    left as it came."""
    _detect(deployment, "detect-1")
    _segment(deployment, "segment-1", TINY)
    _segment(deployment, "segment-2", SMALL)
    detected = _by_role(_objects(deployment))

    application = _open_as_the_application(deployment)

    def tiny(role: str) -> CompressedRLE:
        (mask,) = detected[role].masks_by(TINY)
        return mask

    moved_counts = _moved(tiny("mask moved"))
    _save(application, MASK_RESOURCE, MaskUpdate, tiny("mask accepted").id, {"review_status": "accepted"})
    _save(
        application,
        MASK_RESOURCE,
        MaskUpdate,
        tiny("mask moved").id,
        _web_mask_update(tiny("mask moved"), moved_counts),
    )
    _reject(application, MASK_RESOURCE, tiny("mask rejected").id)
    _reject(application, BBOX_RESOURCE, detected["box rejected"].boxes[0].id)
    # The legacy interface's object inspector: the entity it read, changed (entityCardOps.ts,
    # `saveInputChange`).
    changed = detected["class changed"].entity
    field = label_field_of(application.info.entity)  # type: ignore[arg-type]
    body = {**changed.model_dump(exclude=SERVER_STAMPS), field: NEW_CLASS}
    BaseService(application, ENTITY_RESOURCE).update(
        changed.id, EntityUpdate.model_validate(body).model_dump(exclude_unset=True)
    )

    after = _objects(deployment)
    return _Reviewed(
        detected=detected,
        reviewed={role: after[found.entity.id] for role, found in detected.items()},
        moved_counts=moved_counts,
    )


def _snapshot(found: _Object) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Everything an object, its boxes and its masks hold."""
    return (
        _content(found.entity),
        sorted((_content(box) for box in found.boxes), key=lambda row: row["id"]),
        sorted((_content(mask) for mask in found.masks), key=lambda row: row["id"]),
    )


# The objects the review leaves holding a person's work: whole, they must come out of every rerun as
# they went in. A rejected mask is deleted: it holds nothing.
HELD = ("mask accepted", "mask moved", "class changed")


class TestReviewThenRerun:
    """What a person decided survives every model running again, masks included."""

    def test_the_review_lands_as_the_person_decided(self, reviewed: _Reviewed) -> None:
        """The premise of the other tests: if the review changed nothing, a rerun of the same
        answers would rewrite the same rows, and 'unchanged' would prove nothing."""
        after = reviewed.reviewed

        def statuses(role: str) -> tuple[list[str], list[str], list[str]]:
            """The statuses of the object's boxes, of its tiny masks and of its small masks."""
            found = after[role]
            return (
                [box.review_status for box in found.boxes],
                [mask.review_status for mask in found.masks_by(TINY)],
                [mask.review_status for mask in found.masks_by(SMALL)],
            )

        assert statuses("mask accepted") == (["pending"], ["accepted"], ["pending"])
        assert statuses("mask moved") == (["pending"], ["accepted"], ["pending"])
        # A reject deletes the row. The object stays: other rows still name it.
        assert statuses("mask rejected") == (["pending"], [], ["pending"])
        assert statuses("box rejected") == ([], ["pending"], ["pending"])
        assert statuses("untouched") == (["pending"], ["pending"], ["pending"])
        # The moved mask keeps the model's provenance, although the interface sent its own.
        moved = after["mask moved"].masks_by(TINY)[0]
        assert (moved.counts.decode(), moved.source_type, _model_of(moved)) == (reviewed.moved_counts, "model", TINY)

    def test_a_class_changed_on_the_object_accepts_its_box_and_every_mask(self, reviewed: _Reviewed) -> None:
        """Accepted side effect of a mask naming its box's object: the person said what
        the object is, and every pending model annotation of it is accepted — the masks too,
        although nobody looked at their outline. They leave the queue, and a rerun keeps them."""
        changed = reviewed.reviewed["class changed"]

        assert changed.label == NEW_CLASS
        assert [box.review_status for box in changed.boxes] == ["accepted"]
        assert sorted(mask.review_status for mask in changed.masks) == ["accepted", "accepted"]

    def test_rerunning_both_models_leaves_the_review_alone(self, deployment: _Deployment, reviewed: _Reviewed) -> None:
        """An object a person outlined gets no new mask from either model — and loses the other
        model's pending one; an object whose mask was rejected is outlined again; an object whose
        box was rejected loses its pending masks; the object nobody touched keeps one mask per
        model, pending."""
        before = {role: _snapshot(reviewed.reviewed[role]) for role in HELD}

        _segment(deployment, "segment-3", TINY)
        _segment(deployment, "segment-4", SMALL)

        after = {role: _objects(deployment)[found.entity.id] for role, found in reviewed.reviewed.items()}
        for role in ("mask accepted", "mask moved"):
            assert [_content(mask) for mask in after[role].masks] == [
                _content(mask) for mask in reviewed.reviewed[role].masks_by(TINY)
            ], role
            assert _snapshot(after[role])[:2] == before[role][:2], role
        assert _snapshot(after["class changed"]) == before["class changed"]
        # Accepted consequence of a reject being a delete: the rejected mask left no trace, so the
        # tiny model outlines the object again, pending.
        rejected_mask = reviewed.reviewed["mask rejected"]
        assert _snapshot(after["mask rejected"])[:2] == _snapshot(rejected_mask)[:2]
        assert sorted((_model_of(mask), mask.review_status) for mask in after["mask rejected"].masks) == [
            (SMALL, "pending"),
            (TINY, "pending"),
        ]
        # Known defect (backend-processing §18): no box prompts the object whose box was rejected,
        # so its pending masks go, and the object stays, named by nothing, until a rerun of the
        # detection model that proposed the box sweeps it.
        assert (after["box rejected"].boxes, after["box rejected"].masks) == ([], [])
        assert sorted((_model_of(mask), mask.review_status) for mask in after["untouched"].masks) == [
            (SMALL, "pending"),
            (TINY, "pending"),
        ]

    def test_rerunning_the_detection_too_rewrites_only_what_nobody_reviewed(
        self, deployment: _Deployment, reviewed: _Reviewed
    ) -> None:
        """An object a person outlined keeps its box, and the detector does not
        propose it again beside it; the objects nobody accepted anything of are rewritten, and
        their pending masks go with them; the box a person rejected is proposed again. Then a
        segmentation gives the rewritten objects their masks again."""
        _segment(deployment, "segment-3", TINY)
        _segment(deployment, "segment-4", SMALL)
        before = {role: _snapshot(_objects(deployment)[reviewed.reviewed[role].entity.id]) for role in HELD}

        _detect(deployment, "detect-2")

        objects = _objects(deployment)
        for role in HELD:
            assert _snapshot(objects[reviewed.reviewed[role].entity.id]) == before[role], role
        # One object, one box, where the person outlined it.
        for role in ("mask accepted", "mask moved"):
            assert [found.entity.id for found in _at(objects, role)] == [reviewed.reviewed[role].entity.id], role
        # Where nobody accepted anything, the detector's box again, pending, with no mask: the
        # object whose mask was rejected, and the box a person rejected, which left no trace.
        for role in ("mask rejected", "box rejected", "untouched"):
            assert [
                (found.label, [box.review_status for box in found.boxes], found.masks) for found in _at(objects, role)
            ] == [(DETECTIONS[role][2], ["pending"], [])], role
        # The detection swept the object the rejected box had left named by nothing.
        assert all(found.boxes or found.masks for found in objects.values())
        # Every mask left is one a person accepted: the pending ones went with the objects the
        # detection rewrote.
        assert {mask.review_status for found in objects.values() for mask in found.masks} == {"accepted"}
        # Known consequence of protecting by class (pinned for boxes in
        # test_review_then_rerun.py): the detector's class for the object a person renamed comes
        # back, pending, beside it.
        renamed = reviewed.reviewed["class changed"].entity.id
        assert sorted((found.label, found.boxes[0].review_status) for found in _at(objects, "class changed")) == [
            (DETECTIONS["class changed"][2], "pending"),
            (NEW_CLASS, "accepted"),
        ]
        assert renamed in {found.entity.id for found in _at(objects, "class changed")}

        _segment(deployment, "segment-5", TINY)

        objects = _objects(deployment)
        pending = sorted(
            (found.label, _model_of(mask))
            for found in objects.values()
            for mask in found.masks
            if mask.review_status == "pending"
        )
        assert pending == sorted(
            (DETECTIONS[role][2], TINY) for role in ("mask rejected", "class changed", "box rejected", "untouched")
        )
        for role in HELD:
            assert _snapshot(objects[reviewed.reviewed[role].entity.id]) == before[role], role


class TestReplacingThePrevious:
    def test_replacing_the_previous_boxes_takes_their_pending_masks_and_spares_a_persons(
        self, deployment: _Deployment
    ) -> None:
        """A detection's `replace_previous` deletes its pending boxes and their objects: the pending
        masks on them go first, so none is left naming an object that is gone. An object a person
        outlined is spared, box, mask and all."""
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        accepted = _by_role(_objects(deployment))["mask accepted"]
        _save(
            _open_as_the_application(deployment),
            MASK_RESOURCE,
            MaskUpdate,
            accepted.masks[0].id,
            {"review_status": "accepted"},
        )
        kept = _snapshot(_objects(deployment)[accepted.entity.id])

        _detect(deployment, "detect-2", replace_previous=True)

        objects = _objects(deployment)
        assert _snapshot(objects[accepted.entity.id]) == kept
        assert len(objects) == len(DETECTIONS)
        masks = [mask for found in objects.values() for mask in found.masks]
        assert [mask.review_status for mask in masks] == ["accepted"]

    def test_replacing_the_previous_masks_leaves_the_boxes_and_objects(self, deployment: _Deployment) -> None:
        """A segmentation's `replace_previous` clears both models' pending masks before writing its
        own; the detection's boxes and objects are not its to touch."""
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        _segment(deployment, "segment-2", SMALL)
        boxes_and_objects = {entity_id: _snapshot(found)[:2] for entity_id, found in _objects(deployment).items()}

        _segment(deployment, "segment-3", TINY, replace_previous=True)

        objects = _objects(deployment)
        assert {entity_id: _snapshot(found)[:2] for entity_id, found in objects.items()} == boxes_and_objects
        assert sorted(_model_of(mask) for found in objects.values() for mask in found.masks) == [TINY] * len(
            DETECTIONS
        )


class TestTheMasksOfAnObjectAPersonHolds:
    """A model's pending masks go with their object only when a detection rewrites the object at
    a rank no review froze, or sweeps it. On an object a person holds — its box accepted, or one of
    its masks — they stay, whichever model wrote them. Nothing else pins it: in the review scenario
    above, the segmentation reruns have removed those masks before the detection runs again."""

    @staticmethod
    def _segmented_by_both_models(deployment: _Deployment) -> dict[str, _Object]:
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        _segment(deployment, "segment-2", SMALL)
        return _by_role(_objects(deployment))

    @staticmethod
    def _rewrote_the_untouched_object(deployment: _Deployment, untouched: _Object) -> bool:
        """The premise: the rerun did take the pending masks of an object it rewrote."""
        return _objects(deployment)[untouched.entity.id].masks == []

    @pytest.mark.parametrize("replace_previous", [False, True])
    def test_both_models_masks_stay_on_an_object_whose_box_a_person_accepted(
        self, deployment: _Deployment, replace_previous: bool
    ) -> None:
        objects = self._segmented_by_both_models(deployment)
        car = objects["mask accepted"]
        _save(
            _open_as_the_application(deployment),
            BBOX_RESOURCE,
            BBoxUpdate,
            car.boxes[0].id,
            {"review_status": "accepted"},
        )
        held = _objects(deployment)[car.entity.id]
        assert [box.review_status for box in held.boxes] == ["accepted"]
        assert sorted((_model_of(mask), mask.review_status) for mask in held.masks) == [
            (SMALL, "pending"),
            (TINY, "pending"),
        ]

        _detect(deployment, "detect-2", replace_previous=replace_previous)

        assert _snapshot(_objects(deployment)[car.entity.id]) == _snapshot(held)
        assert self._rewrote_the_untouched_object(deployment, objects["untouched"])

    @pytest.mark.parametrize("replace_previous", [False, True])
    def test_the_other_models_mask_stays_on_an_object_whose_mask_a_person_accepted(
        self, deployment: _Deployment, replace_previous: bool
    ) -> None:
        objects = self._segmented_by_both_models(deployment)
        car = objects["mask accepted"]
        (tiny,) = car.masks_by(TINY)
        _save(_open_as_the_application(deployment), MASK_RESOURCE, MaskUpdate, tiny.id, {"review_status": "accepted"})
        held = _objects(deployment)[car.entity.id]
        assert [mask.review_status for mask in held.masks_by(SMALL)] == ["pending"]

        _detect(deployment, "detect-2", replace_previous=replace_previous)

        assert _snapshot(_objects(deployment)[car.entity.id]) == _snapshot(held)
        assert self._rewrote_the_untouched_object(deployment, objects["untouched"])


class TestKnownConsequenceOfAReassignment:
    """The new interface changes an object's class one annotation at a time: it creates the new
    object, then points the annotation at it. With a box and a mask on one object, each gesture
    leaves the other annotation on the old object. Behaviour kept on purpose, and checked here, so
    that changing it is a decision, not an accident."""

    def test_a_mask_given_another_object_gets_a_proposal_of_the_old_one_beside_it(
        self, deployment: _Deployment
    ) -> None:
        """The box still names the detector's car; a person's mask protects only masks of its own
        class, so the next segmentation outlines the car again, pending, at the same place."""
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        car = _by_role(_objects(deployment))["mask accepted"]
        application = _open_as_the_application(deployment)
        _create_entity(application, NEW_CLASS)
        mask = car.masks[0]
        _save(
            application,
            MASK_RESOURCE,
            MaskUpdate,
            mask.id,
            _web_mask_update(mask, mask.counts.decode(), NEW_ENTITY_ID),
        )

        _segment(deployment, "segment-2", TINY)

        objects = _objects(deployment)
        # The person's mask, on the truck: accepted, kept.
        assert [mask.review_status for mask in objects[NEW_ENTITY_ID].masks] == ["accepted"]
        # The car's box, still pending, prompts again: a second mask at the same place.
        assert [(mask.review_status, _bounds(mask)) for mask in objects[car.entity.id].masks] == [
            ("pending", DETECTIONS["mask accepted"][0])
        ]

    def test_a_box_given_another_object_leaves_the_old_object_named_by_nothing(self, deployment: _Deployment) -> None:
        """The mask still names the car, so the reassignment does not prune it. The next
        segmentation outlines the box's new object instead, and the car is left at its frozen
        rank, named by nothing; the detector proposes a car there again."""
        _detect(deployment, "detect-1")
        _segment(deployment, "segment-1", TINY)
        car = _by_role(_objects(deployment))["mask accepted"]
        application = _open_as_the_application(deployment)
        _create_entity(application, NEW_CLASS)
        _save(application, BBOX_RESOURCE, BBoxUpdate, car.boxes[0].id, _web_box_update(car.boxes[0], NEW_ENTITY_ID))
        assert _objects(deployment)[car.entity.id].masks, "the reassignment pruned the object its mask names"

        _segment(deployment, "segment-2", TINY)
        _detect(deployment, "detect-2")

        objects = _objects(deployment)
        orphan = objects[car.entity.id]
        assert (orphan.boxes, orphan.masks) == ([], [])
        assert [mask.review_status for mask in objects[NEW_ENTITY_ID].masks] == ["pending"]
        assert sorted((found.label, found.boxes[0].review_status) for found in _at(objects, "mask accepted")) == [
            (DETECTIONS["mask accepted"][2], "pending"),
            (NEW_CLASS, "accepted"),
        ]
