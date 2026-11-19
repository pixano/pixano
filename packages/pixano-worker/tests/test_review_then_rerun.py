# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a person decided about a detection's boxes survives the model running again.

Each side runs its own code. The person reviews through pixano's annotation service, on a
dataset instance opened the way the application opens one, with the bodies the annotation
interface sends. The detection runs as the worker's runner composes it, without the queue: planned
on the dataset reopened for the job, then each chunk processed and written through the runner's
own reader and writer. Only the inference server is a stand-in.

Each side's own tests check its half of the contract. These tests check that the halves agree. A
change on one side that the other does not follow fails here: a status the writer would not count
as reviewed, or a provenance, a score or an identifier the review would rewrite.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image as PILImage
from pixano_worker import runner
from pixano_worker.kinds import DetectionKind
from pixano_worker.kinds.detection import DETECTION_CAPABILITY
from pixano_worker.media import MediaResolver

from pixano.api.models import BBoxUpdate, EntityCreate, EntityUpdate
from pixano.api.resources import BBOX_RESOURCE, ENTITY_RESOURCE
from pixano.api.service import BaseService
from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.io import ImportSpec, export_dataset, import_dataset
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.schemas import BBox, Entity, Image, Record, label_field_of


DATASET_ID = "review"
RECORD_ID = "r1"
VIEW_ID = "v1"
MODEL = "yolo"
# Another detection model the inference serves, for a run that replaces the first one's boxes.
OTHER_MODEL = "detr"
WIDTH, HEIGHT = 200, 100

IMAGE_FILE = f"{VIEW_ID}.png"
# The same media storage, mounted elsewhere by the inference: the worker sends it this path.
INFERENCE_MEDIA_ROOT = "/inference-media"

# What the model finds on the image, at every run: pixel corners, score and class. The key names
# what the person then does with each box. The boxes do not overlap and their classes differ, so
# what happens to one says nothing about another.
DETECTIONS: dict[str, tuple[list[int], float, str]] = {
    "accepted": ([10, 10, 40, 40], 0.91, "car"),
    "edited": ([60, 10, 90, 40], 0.82, "bus"),
    "rejected": ([110, 10, 140, 40], 0.73, "dog"),
    "pending": ([160, 10, 190, 40], 0.64, "person"),
}
# The boxes a person accepted: as they came, or by saving an edit of them.
REVIEWED = ("accepted", "edited")

# The person drags the box to edit a few pixels to the right.
EDIT_SHIFT_PX = 5

# The class a person gives the model's car instead, and the entity the interface creates for it.
REASSIGNED_CLASS = "truck"
REASSIGNED_ENTITY_ID = "e-truck"

# The annotation interface (ui/apps/web) sends an Accept as the status alone, or riding on the edit,
# and a Reject as the box's delete with `prune_orphan_entity` (payloadBuilders.ts). It sends an
# edit as the whole box, with its own provenance and a confidence of 1 (bboxPayloadBuilder.ts,
# `buildBBoxUpdate`).
WEB_SOURCE = {"source_type": "other", "source_name": "Pixano", "source_metadata": "{}"}
WEB_CONFIDENCE = 1

# The server stamps these on every write. They say when a row was written, not what it holds.
SERVER_STAMPS = frozenset({"created_at", "updated_at"})


class _Inference:
    """The inference server, serving two detection models that each find `DETECTIONS` on the image."""

    def __init__(self, image: str) -> None:
        self.image = image

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def list_models(self) -> list[Any]:
        return [
            SimpleNamespace(name=name, model_path=f"{name}.pt", capability=DETECTION_CAPABILITY)
            for name in (MODEL, OTHER_MODEL)
        ]

    def detection(self, request: Any, **_kwargs: Any) -> Any:
        # The answer is keyed by the image's path as the inference sees it. A path the worker
        # failed to translate finds nothing, and `_run_detection` says so.
        found = list(DETECTIONS.values()) if request.image == self.image else []
        return SimpleNamespace(
            data=SimpleNamespace(
                boxes=[corners for corners, _, _ in found],
                scores=[score for _, score, _ in found],
                classes=[name for _, _, name in found],
            )
        )


@dataclass
class _Deployment:
    """The library the worker and the application share, how the worker designates its media to
    the inference, and the worker's detection kind."""

    library: Path
    media: MediaResolver
    kind: DetectionKind


@pytest.fixture
def deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Deployment:
    """A library holding one dataset: one record, one image on disk, and tables for boxes and objects."""
    # The runner keeps the datasets it opened in a module-level cache. An empty cache keeps the
    # tests independent of each other.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    PILImage.new("RGB", (WIDTH, HEIGHT)).save(media_root / IMAGE_FILE)

    library = tmp_path / "library"
    created = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Review", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
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
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", inference.client)
    return _Deployment(
        library=library,
        media=MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT),
        kind=DetectionKind("http://inference", ""),
    )


def _run_detection(
    deployment: _Deployment,
    job_id: str,
    params: dict[str, Any] | None = None,
    library: Path | None = None,
    dataset_id: str = DATASET_ID,
) -> Any:
    """Run one detection job as the runner runs it, without the queue.

    Planning is the runner's own (`_plan_and_prepare`): the job split on the dataset reopened,
    bypassing the worker's cache, then `prepare` under the dataset's write lock. Then each chunk is
    processed and written through the runner's own reader and writer, which serve that reopened
    dataset from the cache.

    Args:
        deployment: The library, media and kind under test.
        job_id: The job.
        params: The job's parameters, `MODEL` alone by default.
        library: Another library than the deployment's, for a dataset imported elsewhere.
        dataset_id: The dataset the job runs on.

    Returns:
        The dataset instance the job wrote through.
    """
    library, media, kind = library or deployment.library, deployment.media, deployment.kind
    params = kind.validate_params(params or {"model": MODEL})
    chunks = runner._plan_and_prepare(kind, library, dataset_id, media, job_id, params, threading.Event())
    found = []
    for chunk in chunks:
        result = kind.process(runner._reader_for(library, dataset_id, media), chunk.payload, params)
        found += [len(medium["boxes"]) for medium in result["media"]]
        writer = runner._writer_for(library, dataset_id, kind, job_id, params)
        kind.write(writer, result, chunk.payload, params)
    # Every run sees every object again, the reviewed ones included. What the writer then leaves
    # alone, it leaves by its own decision.
    assert found == [len(DETECTIONS)], "the model did not find its boxes on the image"
    return writer.dataset


def _open_as_the_application(library: Path) -> Dataset:
    """The dataset as the application opens it for a request (`get_dataset_dep`): an instance of its own."""
    return Dataset.find(DATASET_ID, library)


def _save_box_edit(dataset: Dataset, box_id: str, body: dict[str, Any]) -> None:
    """Send a box update the way the annotation interface's Save does, through the application's route.

    The interface strips the id and always asks to prune an entity that the edit leaves without
    annotations (api/annotations.ts, `updateAnnotation`). The route reads the body through its
    transport model and hands the fields that were set to the service (api/routers/resources.py).
    """
    patch = {key: value for key, value in body.items() if key != "id"}
    payload = BBoxUpdate.model_validate(patch).model_dump(exclude_unset=True)
    BaseService(dataset, BBOX_RESOURCE).update(box_id, payload, prune_orphan_entity=True)


def _save_reject(dataset: Dataset, box_id: str) -> None:
    """Send a Reject the way the annotation interface's Save does: the box's delete, asking to prune
    the entity nothing else names (api/annotations.ts, `deleteAnnotation`)."""
    BaseService(dataset, BBOX_RESOURCE).delete(box_id, prune_orphan_entity=True)


def _save_entity_edit(dataset: Dataset, entity_id: str, **changes: Any) -> None:
    """Send an entity edit the way the legacy interface's object inspector does: the entity it
    read, changed (entityCardOps.ts, `saveInputChange`), through the application's route."""
    read = dataset.get_data("entities", ids=[entity_id])[0]
    body = {**read.model_dump(exclude=SERVER_STAMPS), **changes}
    payload = EntityUpdate.model_validate(body).model_dump(exclude_unset=True)
    BaseService(dataset, ENTITY_RESOURCE).update(entity_id, payload)


def _web_box_update(box: BBox, coords: list[float], entity_id: str | None = None) -> dict[str, Any]:
    """The body `buildBBoxUpdate` builds for a box that was moved or given another entity."""
    return {
        "id": box.id,
        "record_id": box.record_id,
        "entity_id": entity_id or box.entity_id,
        "view_id": box.view_id,
        "coords": coords,
        "format": "xywh",
        "is_normalized": True,
        "confidence": WEB_CONFIDENCE,
        **WEB_SOURCE,
    }


def _xywh(corners: list[int]) -> list[float]:
    """Pixel corners as the normalised top-left and size the boxes are stored in."""
    left, top, right, bottom = corners
    return [left / WIDTH, top / HEIGHT, (right - left) / WIDTH, (bottom - top) / HEIGHT]


@dataclass(frozen=True)
class _Box:
    """A stored box and the entity it names, as one reads them back."""

    row: BBox
    entity: Any
    label: str

    def content(self, *ignoring: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Everything the box and its entity hold, apart from when they were written and `ignoring`."""
        excluded = SERVER_STAMPS | set(ignoring)
        return self.row.model_dump(exclude=excluded), self.entity.model_dump(exclude=excluded)


def _label_field(dataset: Dataset) -> str:
    """The entity field holding a class — the detection job gave the dataset one."""
    assert dataset.info.entity is not None
    field = label_field_of(dataset.info.entity)
    assert field is not None
    return field


def _stored_boxes(library: Path) -> list[_Box]:
    """Every box of the dataset, with its entity and class, read through a newly opened instance."""
    dataset = Dataset(library / DATASET_ID)
    field = _label_field(dataset)
    entities = {entity.id: entity for entity in dataset.get_data("entities", limit=None)}
    return [
        _Box(box, entities[box.entity_id], getattr(entities[box.entity_id], field))
        for box in dataset.get_data("bboxes", limit=None)
    ]


def _by_role(boxes: list[_Box]) -> dict[str, _Box]:
    """The first run's boxes, each under the name of what the person does with it."""
    found: dict[str, _Box] = {}
    for role, (corners, _, _) in DETECTIONS.items():
        there = [box for box in boxes if box.row.coords == pytest.approx(_xywh(corners))]
        assert len(there) == 1, f"{len(there)} box(es) where the model found the box to be {role}"
        found[role] = there[0]
    return found


@dataclass(frozen=True)
class _Reviewed:
    """A detection's boxes before and after a person reviewed them, and the instances involved.

    The rejected box has no entry in ``reviewed``: rejecting it deleted it.
    """

    detected: dict[str, _Box]
    reviewed: dict[str, _Box]
    edited_coords: list[float]
    first_job_dataset: Any
    application_dataset: Dataset


@pytest.fixture
def reviewed(deployment: _Deployment) -> _Reviewed:
    """A first detection, then a person accepts one box, edits one, rejects one and leaves the fourth."""
    first_job_dataset = _run_detection(deployment, "job-1")
    detected = _by_role(_stored_boxes(deployment.library))

    application = _open_as_the_application(deployment.library)
    edited = detected["edited"].row
    edited_coords = [edited.coords[0] + EDIT_SHIFT_PX / WIDTH, *edited.coords[1:]]
    _save_box_edit(application, detected["accepted"].row.id, {"review_status": "accepted"})
    _save_box_edit(application, edited.id, _web_box_update(edited, edited_coords))
    _save_reject(application, detected["rejected"].row.id)

    after_review = {box.row.id: box for box in _stored_boxes(deployment.library)}
    return _Reviewed(
        detected=detected,
        reviewed={role: after_review[box.row.id] for role, box in detected.items() if box.row.id in after_review},
        edited_coords=edited_coords,
        first_job_dataset=first_job_dataset,
        application_dataset=application,
    )


class TestReviewThenRerun:
    """A rerun of the model leaves alone what a person accepted."""

    def test_the_review_lands_as_the_person_decided(self, reviewed: _Reviewed) -> None:
        """The premise of the other tests. If the review changed nothing, a rerun of the same
        detections would rewrite the same rows, and 'unchanged' would prove nothing."""
        detected, after = reviewed.detected, reviewed.reviewed

        assert {role: box.row.review_status for role, box in detected.items()} == dict.fromkeys(DETECTIONS, "pending")
        assert {role: box.row.review_status for role, box in after.items()} == {
            "accepted": "accepted",
            "edited": "accepted",
            "pending": "pending",
        }
        # An Accept changes the status alone. The saved edit changes the geometry too, and keeps
        # the model's provenance and score, although the interface sent its own and a confidence of 1.
        for role, box in after.items():
            changed = ("review_status", "coords") if role == "edited" else ("review_status",)
            assert box.content(*changed) == detected[role].content(*changed), role
        assert after["edited"].row.coords == pytest.approx(reviewed.edited_coords)
        assert [(box.row.source_type, box.row.confidence, box.label) for box in after.values()] == [
            ("model", pytest.approx(score), name) for role, (_, score, name) in DETECTIONS.items() if role in after
        ]
        # The rejected box is gone, and its entity with it, since nothing else named it.
        rejected = detected["rejected"]
        stored = Dataset(reviewed.application_dataset.path)
        assert stored.get_data("bboxes", ids=[rejected.row.id]) == []
        assert stored.get_data("entities", ids=[rejected.entity.id]) == []

    def test_a_rerun_leaves_the_reviewed_boxes_as_they_were(
        self, deployment: _Deployment, reviewed: _Reviewed
    ) -> None:
        """Accepted boxes, edited or not, keep their identifier, status, geometry, provenance,
        score and entity."""
        rerun_dataset = _run_detection(deployment, "job-2")

        assert rerun_dataset is not reviewed.application_dataset, "the rerun wrote through the review's instance"
        assert rerun_dataset is not reviewed.first_job_dataset, "the rerun read an instance opened before the review"
        after = {box.row.id: box for box in _stored_boxes(deployment.library)}
        for role in REVIEWED:
            box = reviewed.reviewed[role]
            assert box.row.id in after, f"the {role} box is gone"
            assert after[box.row.id].content() == box.content(), role


class TestAcceptedConsequenceOfARejectBeingADelete:
    """Decided with the review's design: a rejected box is deleted and leaves no trace, so nothing
    keeps the model from proposing it again. Checked here so that changing it is a decision, not an
    accident."""

    def test_a_rerun_proposes_the_rejected_box_again(self, deployment: _Deployment, reviewed: _Reviewed) -> None:
        """The model finds the rejected object again, at the same place and with the same class,
        and proposes it: pending, for the reviewer to reject again."""
        rejected = reviewed.detected["rejected"]

        _run_detection(deployment, "job-2")

        same_class = [
            (box.row.review_status, box.row.source_type, box.row.coords)
            for box in _stored_boxes(deployment.library)
            if box.label == rejected.label
        ]
        assert same_class == [("pending", "model", pytest.approx(rejected.row.coords))]


class TestEditsOutsideTheBox:
    """What a person changes about a detection without touching its box is an edit all the same."""

    def test_a_class_fixed_on_the_object_survives_a_rerun(self, deployment: _Deployment) -> None:
        """The legacy interface fixes a class by editing the object the box names. The box stayed
        pending, so the next run wrote the model's class back over the person's."""
        _run_detection(deployment, "job-1")
        (box,) = [box for box in _stored_boxes(deployment.library) if box.label == DETECTIONS["pending"][2]]
        application = _open_as_the_application(deployment.library)

        _save_entity_edit(application, box.entity.id, **{_label_field(application): REASSIGNED_CLASS})

        (relabelled,) = [found for found in _stored_boxes(deployment.library) if found.row.id == box.row.id]
        assert (relabelled.label, relabelled.row.review_status) == (REASSIGNED_CLASS, "accepted")
        _run_detection(deployment, "job-2")
        after = {found.row.id: found for found in _stored_boxes(deployment.library)}
        assert after[box.row.id].content() == relabelled.content()


class TestAReimportedDetection:
    """A JSONL export does not carry the review status: a model's box comes back without one."""

    def test_replacing_the_previous_boxes_clears_the_reimported_ones(
        self, deployment: _Deployment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nobody reviewed them, as the application reads them. `replace_previous` left them, and
        the record held the first model's boxes and the second one's at the same places."""
        _run_detection(deployment, "job-1")
        exported = export_dataset(Dataset(deployment.library / DATASET_ID), tmp_path / "exported", media="uris")
        spec = ImportSpec.from_yaml(exported / "dataset.yaml")
        # The image's absolute path, as the worker resolves it, rather than one under a server.
        spec.media.uri_prefix = "/"
        imported = import_dataset(exported, tmp_path / "data", spec, importer=PixanoJsonlImporter()).dataset_path
        reimported = Dataset(imported)
        assert {(box.source_type, box.review_status) for box in reimported.get_data("bboxes", limit=None)} == {
            ("model", "")
        }
        monkeypatch.setattr(runner, "_open_datasets", OrderedDict())

        _run_detection(
            deployment,
            "job-2",
            {"model": OTHER_MODEL, "replace_previous": True},
            library=imported.parent,
            dataset_id=reimported.info.id,
        )

        boxes = Dataset(imported).get_data("bboxes", limit=None)
        assert len(boxes) == len(DETECTIONS)
        assert all(OTHER_MODEL in box.source_metadata and box.review_status == "pending" for box in boxes)


class TestKnownConsequenceOfSameClassProtection:
    """Behaviour kept on purpose. It is checked here so that changing it is
    a decision, not an accident."""

    def test_a_box_given_another_class_gets_a_new_proposal_of_the_models_class(self, deployment: _Deployment) -> None:
        """A person says the model's car is a truck, through the interface's reassignment. A
        person's box protects only against detections of its own class, so on the next run the
        model proposes its car again, pending, at the same place. The truck stays as the person
        left it, and the reviewer has to reject the car again."""
        car_class = DETECTIONS["accepted"][2]
        _run_detection(deployment, "job-1")
        (car,) = [box for box in _stored_boxes(deployment.library) if box.label == car_class]
        application = _open_as_the_application(deployment.library)
        field = _label_field(application)
        # What the interface queues for a reassignment to a new entity: the entity's create
        # (buildPayloads.ts, `buildEntityCreateMutation`), then the box's update naming it.
        new_entity = {"id": REASSIGNED_ENTITY_ID, "record_id": RECORD_ID, "parent_id": "", field: REASSIGNED_CLASS}
        BaseService(application, ENTITY_RESOURCE).create(EntityCreate.model_validate(new_entity).model_dump())
        _save_box_edit(application, car.row.id, _web_box_update(car.row, car.row.coords, REASSIGNED_ENTITY_ID))
        (truck,) = [box for box in _stored_boxes(deployment.library) if box.row.id == car.row.id]
        assert (truck.label, truck.row.review_status) == (REASSIGNED_CLASS, "accepted")

        _run_detection(deployment, "job-2")

        at_its_place = [box for box in _stored_boxes(deployment.library) if box.row.coords == car.row.coords]
        assert [box.content() for box in at_its_place if box.row.id == truck.row.id] == [truck.content()]
        # Known behaviour: the model's car comes back next to the person's truck, as a new
        # pending proposal, because a person's box only covers detections of its own class.
        assert [
            (box.label, box.row.review_status, box.row.source_type)
            for box in at_its_place
            if box.row.id != truck.row.id
        ] == [(car_class, "pending", "model")]
