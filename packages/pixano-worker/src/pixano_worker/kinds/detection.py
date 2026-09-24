# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The detection job kind: boxes and the objects they name, proposed by a model for review.

Each medium is sent on its own — the inference's detection endpoint takes one image per call —
and every box comes back as a pre-annotation: a row in the boxes table, pending review, and the
object it names in the entities table, its class in the field the interface reads a class from.

A person's work is never contradicted. A box someone drew, accepted, corrected or rejected is
left alone by a rerun, and a detection that mostly covers such a box, for the same class, is not
written: the person has already said what is there.
"""

import logging
import time
from typing import Any, Iterable

import httpx
from PIL import Image, UnidentifiedImageError
from pixano_inference_client import DetectionRequest, PixanoInferenceError, SyncPixanoInferenceClient
from pydantic import Field

from pixano.inference.types import TASK_TO_CAPABILITY, InferenceTask
from pixano.schemas import DEFAULT_LABEL_FIELD, label_field_of
from pixano.utils.python import to_sql_list

from ..reader import JobReader, MediaType
from ..writer import ENTITY_TABLE, MODEL_SOURCE, JobWriter, ModelIdentity, is_reviewed
from .base import (
    CONFIRM_MARKER,
    MODEL_TASK_MARKER,
    Chunk,
    JobKind,
    JobParams,
    Outcome,
    QuarantinedItem,
    TransientError,
    media_chunks,
)
from .inference import InferenceServer, blame_the_server_or_the_media, classify, refusal_detail


log = logging.getLogger("pixano-worker")

# The task of the model this kind calls, in Pixano's vocabulary — the one the form sends to the
# application to list the served models — and the same task in pixano-inference's, which the
# worker asks the server about. The two differ for some tasks (segmentation), hence one source.
DETECTION_TASK = InferenceTask.DETECTION
DETECTION_CAPABILITY = TASK_TO_CAPABILITY[DETECTION_TASK]

# The canonical table of a dataset's bounding boxes.
BBOX_TABLE = "bboxes"

# The layout the boxes are written in: the one the annotation interface draws from.
BOX_FORMAT = "xywh"

Box = tuple[float, float, float, float]


class DetectionParams(JobParams):
    """Parameters of the detection job.

    Attributes:
        model: The model name as the inference declares it.
        media: The media types to run the model on. Only images can be sent today; another type
            refuses the whole job.
        classes: The classes to look for. An open-vocabulary model is asked for them; any model
            keeps only those — a closed-vocabulary one ignores the request and answers with
            every class it knows. Empty, the model finds the classes it was trained on.
        box_threshold: The score below which the model keeps no box.
        overlap_threshold: A detection whose overlap (intersection over union) with a box a
            person drew or reviewed reaches this value, for the same class, is not written. At 1,
            only an exact duplicate is dropped.
        replace_previous: Delete, before detecting, every box this kind wrote that nobody has
            reviewed yet, whatever its model. Without it, a rerun of the same model replaces its
            own boxes and another model's stay. Done once, at planning; the form asks for
            confirmation.
        chunk_size: Media per chunk — as many calls to the inference, one per medium.
        max_retries: Short retries of a call that failed transiently, done by the inference
            client before handing back. Beyond that, the chunk is handed back to the queue.
        request_timeout_s: Beyond this, a call is considered lost. Generous: a model on CPU
            takes time.
    """

    # No default: the model is whichever the inference serves for detection, which the form
    # offers; a name written here would be a guess about a deployment.
    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: DETECTION_TASK.value})
    # A plain default rather than a factory, so that pydantic publishes it and the form starts
    # from it. Pydantic copies a mutable default, so no instance shares the list.
    media: list[MediaType] = Field(default=["image"], min_length=1)
    classes: list[str] = []
    box_threshold: float = Field(default=0.5, ge=0, le=1)
    overlap_threshold: float = Field(default=0.5, gt=0, le=1)
    replace_previous: bool = Field(
        default=False,
        json_schema_extra={
            CONFIRM_MARKER: "This deletes every box a detection job wrote on this dataset that nobody has reviewed "
            "yet, whatever its model, before detecting again."
        },
    )
    chunk_size: int = Field(default=8, ge=1, le=256)
    max_retries: int = Field(default=3, ge=0, le=10)
    request_timeout_s: float = Field(default=300.0, gt=0)


class DetectionKind(JobKind[DetectionParams]):
    """Proposes boxes, and the objects they name, for a person to review."""

    name = "detection"
    params_model = DetectionParams
    # The inference's detection endpoint takes an image.
    supported_media = frozenset({"image"})
    # A detected box is the output of a model, and arrives pending review.
    source_type = MODEL_SOURCE

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {
        "request_timeout_s",
        "max_retries",
        # What the job did to the dataset before detecting, not how a box was found.
        "replace_previous",
    }

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    def model_identity(self, params: DetectionParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it."""
        return self.server.model_identity(params.model)

    def prepare(self, writer: JobWriter, params: DetectionParams) -> None:
        """Give the entities a field for their class, and clear the pending boxes when asked.

        Both are idempotent: the field is added once, and a second clearing finds nothing left.
        Destructive only on the explicit parameter, as the contract requires.
        """
        writer.ensure_label_field()
        if params.replace_previous:
            writer.drop_pending(BBOX_TABLE, with_entities=True)

    def plan(self, reader: JobReader, params: DetectionParams) -> Iterable[Chunk]:
        """Split the chosen media into batches, after checking the job can run at all.

        Raises:
            ValueError: A chosen media type cannot be processed, the dataset has no table to
                hold boxes or objects nor a field to hold a class, or the inference serves no
                such model.
        """
        self.refuse_unsupported_media(params.media)
        tables = reader.dataset.info.tables
        for table in (BBOX_TABLE, ENTITY_TABLE):
            if table not in tables:
                raise ValueError(f"this dataset has no '{table}' table to write detections into")
        entity = tables[ENTITY_TABLE]
        if label_field_of(entity) is None and DEFAULT_LABEL_FIELD in getattr(entity, "model_fields", {}):
            # The field a class would be added as exists with another type: every write would
            # fail on it, chunk after chunk. Said once, here.
            raise ValueError(
                f"this dataset's entities have a '{DEFAULT_LABEL_FIELD}' field that is not text, and no text field "
                "to hold the class of a detected object"
            )
        self.server.require_served(params.model, DETECTION_CAPABILITY)
        yield from media_chunks(reader, params.media, params.chunk_size)

    def process(self, reader: JobReader, payload: dict[str, Any], params: DetectionParams) -> dict[str, Any]:
        """Detect on each medium of a batch, and return its boxes, with the fate of each medium.

        A medium that cannot be found, whose size cannot be known — its boxes could not be
        placed — or that the inference refuses goes to **quarantine**, its record in the detail.
        Otherwise it is **produced**, even with no box: a medium where the model sees nothing is
        an answer.

        The size comes from the view, and from the image itself when the view has none: a
        dataset imported by URI records no size, and quarantining all of it would make it
        impossible to pre-annotate.

        Raises:
            TransientError: The inference does not answer, or refuses every medium through no
                fault of theirs.
        """
        table: str = payload["table"]
        view_ids: list[str] = payload["view_ids"]
        started = time.perf_counter()
        views = {row.id: row for row in reader.rows(table, view_ids)} if view_ids else {}

        quarantined: list[dict[str, Any]] = []
        candidates: list[tuple[Any, str, tuple[int, int]]] = []
        # The media sent by path, so that one can be resent as bytes if the server refuses them
        # all while it still accepts the witness image.
        by_path: dict[str, Any] = {}
        for view_id in view_ids:
            view = views.get(view_id)
            if view is None:
                quarantined.append({"item_id": view_id, "reason": "media not found"})
                continue
            resolved = reader.resolve_media(table, view)
            if resolved is None:
                quarantined.append(
                    {"item_id": view_id, "reason": "media not found", "detail": {"record_id": view.record_id}}
                )
                continue
            size = _recorded_size(view) or _measured_size(reader, table, view)
            if size is None:
                quarantined.append(
                    {"item_id": view_id, "reason": "image size unknown", "detail": {"record_id": view.record_id}}
                )
                continue
            candidates.append((view, resolved.value, size))
            if not resolved.carried_bytes:
                by_path[view_id] = view
        read_s = time.perf_counter() - started

        client = self.server.client(max_retries=params.max_retries)
        started = time.perf_counter()
        media: list[dict[str, Any]] = []
        refused: list[tuple[Any, dict[str, Any]]] = []
        for view, reference, size in candidates:
            try:
                output = self._detect(client, reference, params)
            except (httpx.TransportError, PixanoInferenceError) as error:
                failure = classify(error)
                if failure == "transient":
                    raise TransientError(
                        f"the inference does not answer or asks to come back later: {error}"
                    ) from error
                if failure == "request":
                    raise
                refused.append((view, refusal_detail(error)))  # type: ignore[arg-type]
                continue
            media.append(_medium(view, size, output, params.classes))
        inference_s = time.perf_counter() - started

        if refused and not media:
            blame_the_server_or_the_media(
                lambda reference: self._detect(client, reference, params),
                reader,
                table,
                [view.id for view, _ in refused],
                by_path,
            )
        quarantined.extend(
            {
                "item_id": view.id,
                "reason": "refused by the inference server",
                "detail": {**detail, "record_id": view.record_id},
            }
            for view, detail in refused
        )
        return {"media": media, "quarantined": quarantined, "phases_s": {"read": read_s, "inference": inference_s}}

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """What `process` observed for each medium."""
        return Outcome(
            produced=len(result["media"]),
            skipped=0,
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: DetectionParams
    ) -> None:
        """Write each medium's boxes and their objects, replacing what the same model wrote there.

        A detection that overlaps, by `overlap_threshold` or more, a box a person drew or
        reviewed, for the same class, is dropped: that box already says what is there. A
        person's box without a class stands for any class.
        """
        started = time.perf_counter()
        # Again here and not only at planning: a worker whose dataset was opened before the
        # field was added still holds the schema without it.
        field = writer.ensure_label_field()
        bbox_schema = writer.table_schema(BBOX_TABLE)
        entity_schema = writer.table_schema(ENTITY_TABLE)
        written = dropped = 0
        for medium in result["media"]:
            protected = self._protected_boxes(writer, medium, field)
            boxes, entities = [], []
            for coords, score, name in zip(medium["boxes"], medium["scores"], medium["classes"], strict=True):
                if _covered(coords, name, protected, params.overlap_threshold):
                    dropped += 1
                    continue
                boxes.append(
                    bbox_schema(
                        id="",
                        record_id=medium["record_id"],
                        view_id=medium["view_id"],
                        coords=list(coords),
                        format=BOX_FORMAT,
                        is_normalized=True,
                        confidence=min(max(score, 0.0), 1.0),
                        **writer.provenance(),
                    )
                )
                entities.append(entity_schema(id="", record_id=medium["record_id"], **{field: name}))
            written += len(writer.replace(BBOX_TABLE, medium["view_id"], boxes, entities))
        phases = result.get("phases_s", {})
        log.info(
            "job %s: phases read %.3f s, inference %.3f s, write %.3f s (%d box(es), %d left to a person's box)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("inference", 0.0),
            time.perf_counter() - started,
            written,
            dropped,
        )

    @staticmethod
    def _protected_boxes(writer: JobWriter, medium: dict[str, Any], field: str) -> list[tuple[Box, str]]:
        """The boxes of a medium a detection must not contradict, with their class, "" if none.

        A box a person drew — anything but a model's output — or one a person reviewed.
        """
        rows = [
            row
            for row in writer.read(BBOX_TABLE, f"view_id IN {to_sql_list(medium['view_id'])}")
            if row.source_type != MODEL_SOURCE or is_reviewed(row)
        ]
        entity_ids = {row.entity_id for row in rows if row.entity_id}
        entities = writer.read(ENTITY_TABLE, f"id IN {to_sql_list(entity_ids)}") if entity_ids else []
        classes = {entity.id: getattr(entity, field, "") for entity in entities}
        return [
            (_normalized_xyxy(row, medium["width"], medium["height"]), classes.get(row.entity_id, "")) for row in rows
        ]

    @staticmethod
    def _detect(client: SyncPixanoInferenceClient, reference: str, params: DetectionParams) -> Any:
        """One detection call, on one image."""
        request = DetectionRequest(
            model=params.model,
            image=reference,
            classes=params.classes or None,
            box_threshold=params.box_threshold,
        )
        return client.detection(request, timeout=params.request_timeout_s).data


def _recorded_size(view: Any) -> tuple[int, int] | None:
    """The image's size as the dataset records it, if it does."""
    width, height = getattr(view, "width", 0), getattr(view, "height", 0)
    return (width, height) if width > 0 and height > 0 else None


def _measured_size(reader: JobReader, table: str, view: Any) -> tuple[int, int] | None:
    """The image's size read from its header, when the dataset does not record it.

    From its file for a view imported by reference — such a view carries no bytes — and from
    its bytes for an embedded one.
    """
    media = reader.open_media(table, view)
    if media is None:
        return None
    try:
        with media, Image.open(media) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None


def _medium(view: Any, size: tuple[int, int], output: Any, wanted: list[str]) -> dict[str, Any]:
    """A medium's detections, placed as the dataset stores them: normalised, top-left and size.

    The server answers in pixels, corners; a box that the image's bounds reduce to nothing is
    not one. Only the classes asked for are kept, when some are, case aside.
    """
    width, height = size
    kept = {name.casefold() for name in wanted}
    boxes, scores, classes = [], [], []
    for (x1, y1, x2, y2), score, name in zip(output.boxes, output.scores, output.classes, strict=True):
        if kept and str(name).casefold() not in kept:
            continue
        left, top = min(max(x1, 0), width), min(max(y1, 0), height)
        right, bottom = min(max(x2, 0), width), min(max(y2, 0), height)
        if right <= left or bottom <= top:
            continue
        boxes.append([left / width, top / height, (right - left) / width, (bottom - top) / height])
        scores.append(float(score))
        classes.append(str(name))
    return {
        "view_id": view.id,
        "record_id": view.record_id,
        "width": width,
        "height": height,
        "boxes": boxes,
        "scores": scores,
        "classes": classes,
    }


def _normalized_xyxy(row: Any, width: int, height: int) -> Box:
    """A stored box as normalised corners, whatever layout it was stored in."""
    x, y, a, b = row.coords
    if row.format == BOX_FORMAT:
        a, b = x + a, y + b
    if not row.is_normalized:
        x, a = x / width, a / width
        y, b = y / height, b / height
    return x, y, a, b


def _covered(coords: list[float], name: str, protected: list[tuple[Box, str]], threshold: float) -> bool:
    """Whether a person's box already says what this detection says."""
    x, y, w, h = coords
    box = (x, y, x + w, y + h)
    return any(
        (not other_class or other_class.casefold() == name.casefold()) and iou(box, other) >= threshold
        for other, other_class in protected
    )


def iou(first: Box, second: Box) -> float:
    """Intersection over union of two boxes given as corners."""
    width = min(first[2], second[2]) - max(first[0], second[0])
    height = min(first[3], second[3]) - max(first[1], second[1])
    if width <= 0 or height <= 0:
        return 0.0
    intersection = width * height
    union = (
        (first[2] - first[0]) * (first[3] - first[1])
        + (second[2] - second[0]) * (second[3] - second[1])
        - intersection
    )
    return intersection / union if union > 0 else 0.0
