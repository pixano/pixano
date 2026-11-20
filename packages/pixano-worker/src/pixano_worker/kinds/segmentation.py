# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The segmentation job kind: a mask for each box already on an image, proposed by a model for review.

A segmentation model outlines what a box points at: it takes an image and boxes, and answers one
mask per box. The boxes are the ones already on each image — a detection's or a person's, whatever
their model or status — so this kind runs after them: detection, then segmentation, two jobs
chained by hand until workflows exist. An image without such a box is skipped; nothing is asked
about it.

Each mask names the object of the box that prompted it: the object carries its box and its mask,
and a person who fixes its class fixes both. Masks arrive pending review, and a rerun of the same
model replaces only those still pending; another model's masks add to them.

A person's work is never contradicted. An object that already holds a mask someone drew or
accepted gets none, from any model; and a mask that mostly covers such a mask on another object,
of the same class, is not written: the person has already said what is there.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Sequence

import httpx
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_inference.schemas import SegmentationRequest
from pydantic import Field

from pixano.inference.types import TASK_TO_CAPABILITY, InferenceTask
from pixano.schemas import label_field_of
from pixano.schemas.table_names import canonical_table_name_for_slot
from pixano.utils.python import to_sql_list

from ..reader import JobReader, MediaType
from ..writer import ENTITY_TABLE, MODEL_SOURCE, JobWriter, ModelIdentity, is_a_persons_work
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
from .inference import (
    REFUSED_BY_THE_SERVER,
    WITNESS_IMAGE_SIDE,
    InferenceServer,
    blame_the_server_or_the_media,
    chunk_media,
    classify,
    quarantined_item,
    refusal_detail,
)
from .masks import covered, is_empty, is_readable, pixel_prompt


log = logging.getLogger("pixano-worker")

# The task of the model this kind calls, in Pixano's vocabulary — the one the form sends to the
# application to list the served models — and in pixano-inference's, which the worker asks the
# server about: `image_mask_generation` there, `segmentation` here.
SEGMENTATION_TASK = InferenceTask.MASK_GENERATION
SEGMENTATION_CAPABILITY = TASK_TO_CAPABILITY[SEGMENTATION_TASK]

# The dataset slot masks are declared under, and the canonical tables this kind reads and writes.
MASK_SLOT = "mask"
MASK_TABLE = canonical_table_name_for_slot(MASK_SLOT)
BBOX_TABLE = canonical_table_name_for_slot("bbox")

# One mask per box. Asked for several, SAM 2 answers three per box, and refuses any other count.
MASKS_PER_PROMPT = 1

# The box sent with the witness image (`blame_the_server_or_the_media`): the segmentation endpoint
# answers a prompt, and this one covers the whole witness. The helper also resends a refused image
# as bytes with the same call; the box is inside any image the server accepts, and the call only
# asks whether the server reads the image, not what is in it.
WITNESS_PROMPT = [0, 0, WITNESS_IMAGE_SIDE, WITNESS_IMAGE_SIDE]

# The image encoder dominates a call, whatever the number of boxes. Measured per image: 1.6 to 2.0 s
# natively on an M1 Pro with one thread (2026-10-07), 7 to 7.8 s through the compose's inference
# server with the two CPUs each SAM model is given there (2026-10-09). Eight images make a chunk
# of 15 to 65 s: each call stays under the server's 60 s limit, and a chunk is short enough to
# resume from.
DEFAULT_CHUNK_SIZE = 8
MAX_CHUNK_SIZE = 256
DEFAULT_MAX_RETRIES = 3
MAX_RETRIES = 10
# The server gives a segmentation call 60 s, its queue included, then answers 504 — transient, the
# chunk is replayed. Twice that here, so that the server's answer always arrives before the client
# gives up on it.
DEFAULT_REQUEST_TIMEOUT_S = 120.0
# As detection's: a mask covering a person's by half or more says the same thing.
DEFAULT_OVERLAP_THRESHOLD = 0.5

# How many identifiers a filter names at most when reading the objects a chunk's boxes and masks
# name: a long filter is slow to parse. A chunk of eight images rarely names more than a few dozen.
IDS_PER_READ = 1_000

# Why an image goes to quarantine, as its record in the queue says it.
IMAGE_SIZE_UNKNOWN = "image size unknown"
WRONG_MASK_COUNT = "the inference answered another number of masks than boxes"
MASK_SIZE_DIFFERS = "mask size differs from the image"
UNREADABLE_MASK = "the inference answered an unreadable mask"

# Why a job is refused at planning.
NO_BOX_TO_SEGMENT = "this dataset has no box to segment: run a detection or draw boxes first"


class SegmentationParams(JobParams):
    """Parameters of the segmentation job.

    Attributes:
        model: The model name as the inference declares it.
        media: The media types to run the model on. Only images can be sent today; another type
            refuses the whole job.
        overlap_threshold: A mask whose overlap (intersection over union) with a mask a person
            drew or accepted, on another object of the same class, reaches this value is not
            written. At 1, only an exact duplicate is dropped.
        replace_previous: Delete, before segmenting, every mask this kind wrote that is still
            pending review, whatever its model. Without it, a rerun of the same model replaces its
            own masks and another model's stay. Done once, at planning; the form asks for
            confirmation. The boxes and their objects stay.
        chunk_size: Images per chunk — as many calls to the inference, one per image.
        max_retries: Short retries of a call that failed transiently, done by the inference
            client before handing back. Beyond that, the chunk is handed back to the queue.
        request_timeout_s: Beyond this, a call is considered lost.
    """

    # No default: the model is whichever the inference serves for segmentation, which the form
    # offers; a name written here would be a guess about a deployment.
    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: SEGMENTATION_TASK.value})
    # A plain default rather than a factory, so that pydantic publishes it and the form starts
    # from it. Pydantic copies a mutable default, so no instance shares the list.
    media: list[MediaType] = Field(default=["image"], min_length=1)
    overlap_threshold: float = Field(default=DEFAULT_OVERLAP_THRESHOLD, gt=0, le=1)
    replace_previous: bool = Field(
        default=False,
        json_schema_extra={
            CONFIRM_MARKER: "This deletes every mask a segmentation job wrote on this dataset that is still "
            "pending review, whatever its model, before segmenting again. The boxes and their objects stay."
        },
    )
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=1, le=MAX_CHUNK_SIZE)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0, le=MAX_RETRIES)
    request_timeout_s: float = Field(default=DEFAULT_REQUEST_TIMEOUT_S, gt=0)


@dataclass(frozen=True)
class _Refusal:
    """Why the inference's answer for an image cannot be written, with what tells it."""

    reason: str
    detail: dict[str, Any]


class SegmentationKind(JobKind[SegmentationParams]):
    """Proposes a mask for each box on an image, on the box's object, for a person to review."""

    name = "segmentation"
    params_model = SegmentationParams
    # The inference's segmentation endpoint takes an image.
    supported_media = frozenset({"image"})
    # A mask is the output of a model, and arrives pending review.
    source_type = MODEL_SOURCE

    #: How the engine runs the job, not what it computes: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {
        "request_timeout_s",
        "max_retries",
        # What the job did to the dataset before segmenting, not how a mask was found.
        "replace_previous",
    }

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    def model_identity(self, params: SegmentationParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it."""
        return self.server.model_identity(params.model)

    def prepare(self, writer: JobWriter, params: SegmentationParams) -> None:
        """Give the dataset a masks table if it has none, and clear the pending masks when asked.

        A dataset built with boxes only has no table to hold masks; the job adds
        the canonical one rather than refusing. Both steps are idempotent: the table is added
        once, and a second clearing finds nothing left. Destructive only on the explicit
        parameter, as the contract requires — and then only masks: the boxes and their objects
        belong to whoever made them.
        """
        table = writer.ensure_table(MASK_SLOT)
        if params.replace_previous:
            writer.drop_pending(table, with_entities=False)

    def plan(self, reader: JobReader, params: SegmentationParams) -> Iterable[Chunk]:
        """Split the chosen images into batches, after checking the job can run at all.

        A dataset without a masks table is not refused: `prepare` gives it one. A dataset where no
        box could prompt a mask is, unless the job only clears the previous masks — then there is
        nothing to segment, and clearing is still what was asked.

        Raises:
            ValueError: A chosen media type cannot be processed, the dataset has no table of
                boxes or objects, no box to segment, or the inference serves no such model.
        """
        self.refuse_unsupported_media(params.media)
        tables = reader.dataset.info.tables
        for table in (BBOX_TABLE, ENTITY_TABLE):
            if table not in tables:
                raise ValueError(f"this dataset has no '{table}' table to take the boxes to segment from")
        if not params.replace_previous and not reader.count(BBOX_TABLE, "entity_id != ''"):
            raise ValueError(NO_BOX_TO_SEGMENT)
        self.server.require_served(params.model, SEGMENTATION_CAPABILITY)
        yield from media_chunks(reader, params.media, params.chunk_size)

    def process(self, reader: JobReader, payload: dict[str, Any], params: SegmentationParams) -> dict[str, Any]:
        """Segment the boxes of each image of a batch, and return the masks, with the fate of each image.

        One call per image, with all its boxes: the model encodes the image once and answers each
        box from that. An image without a box to segment — none, or only objects a person already
        outlined — is **skipped**, with no call. One that cannot be found, whose size cannot be
        known — its boxes could not be placed in pixels — or that the inference refuses goes to
        **quarantine**, its record in the detail; so does one whose answer does not fit it: not
        one mask per box, or masks of another size than the image.
        Otherwise it is **produced**, even when every mask came back empty.

        Raises:
            TransientError: The inference does not answer, or refuses every image through no
                fault of theirs.
        """
        table: str = payload["table"]
        started = time.perf_counter()
        found = chunk_media(reader, table, payload["view_ids"])
        quarantined = found.quarantined
        view_ids = [view.id for view, _ in found.media]
        boxes, _ = _prompting_boxes(reader.read, view_ids)
        outlined = (
            _persons_masks(reader.read, view_ids) if MASK_TABLE in reader.dataset.info.tables else defaultdict(list)
        )
        skipped: list[dict[str, Any]] = []
        calls: list[tuple[Any, str, tuple[int, int], list[tuple[Any, list[int]]]]] = []
        for view, reference in found.media:
            held = {mask.entity_id for mask in outlined[view.id]}
            to_segment = [box for box in boxes[view.id] if box.entity_id not in held]
            if not to_segment:
                skipped.append({"view_id": view.id, "record_id": view.record_id})
                continue
            size = reader.image_size(table, view)
            if size is None:
                quarantined.append(quarantined_item(view.id, IMAGE_SIZE_UNKNOWN, view.record_id))
                continue
            prompts = [(box, corners) for box in to_segment if (corners := pixel_prompt(box, *size)) is not None]
            if not prompts:
                skipped.append({"view_id": view.id, "record_id": view.record_id})
                continue
            calls.append((view, reference, size, prompts))
        read_s = time.perf_counter() - started

        media: list[dict[str, Any]] = []
        refused: list[tuple[Any, dict[str, Any]]] = []
        answered = False
        # Closed with the chunk: a client holds a connection pool, and a worker runs thousands
        # of chunks.
        with self.server.client(max_retries=params.max_retries) as client:
            started = time.perf_counter()
            for view, reference, (width, height), prompts in calls:
                try:
                    output = self._segment(client, reference, [corners for _, corners in prompts], params)
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
                answered = True
                masks = _one_mask_per_prompt(output, len(prompts), [height, width])
                if isinstance(masks, _Refusal):
                    quarantined.append(quarantined_item(view.id, masks.reason, view.record_id, **masks.detail))
                    continue
                media.append(
                    {
                        "view_id": view.id,
                        "record_id": view.record_id,
                        "width": width,
                        "height": height,
                        # An empty mask outlines nothing: there is nothing to review, so nothing
                        # to write.
                        "masks": [
                            {
                                "box_id": box.id,
                                "entity_id": box.entity_id,
                                "prompt": corners,
                                "size": list(mask.size),
                                "counts": _text(mask.counts),
                            }
                            for (box, corners), mask in zip(prompts, masks, strict=True)
                            if not is_empty(mask)
                        ],
                    }
                )
            inference_s = time.perf_counter() - started

            # Every image the server was asked about was refused, and it answered none: the
            # witness tells an outage from a chunk of bad images.
            if refused and not answered:
                blame_the_server_or_the_media(
                    lambda reference: self._segment(client, reference, [WITNESS_PROMPT], params),
                    reader,
                    table,
                    [view.id for view, _ in refused],
                    found.by_path,
                )
        quarantined.extend(
            quarantined_item(view.id, REFUSED_BY_THE_SERVER, view.record_id, **detail) for view, detail in refused
        )
        return {
            "media": media,
            "skipped": skipped,
            "quarantined": quarantined,
            "phases_s": {"read": read_s, "inference": inference_s},
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """What `process` observed for each image."""
        return Outcome(
            produced=len(result["media"]),
            skipped=len(result["skipped"]),
            quarantined=[QuarantinedItem.model_validate(item) for item in result["quarantined"]],
        )

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: SegmentationParams
    ) -> None:
        """Write each image's masks on their objects, replacing what the same model wrote there.

        The boxes and the masks a person made are read again first: `process` ran outside the
        write lock. A mask whose box is gone (deleted, or rejected, which deletes it), moved, or
        now names another object or one that is gone is dropped — it outlines what the box no
        longer says. So is a mask on an object a person outlined meanwhile, or over a person's
        mask of the same class. This sees what this worker wrote meanwhile — a detection rerun of
        the same dataset; a review saved through the application during the job may go unseen,
        which is why reviews wait for the job's end (backend-processing §18).

        Every image the chunk read is replaced, the skipped ones with no mask: the pending mask of
        an image whose only box a person deleted (or rejected) since goes with it.
        """
        started = time.perf_counter()
        # Again here and not only at planning: a worker whose dataset was opened before the table
        # was added holds metadata without it.
        table = writer.ensure_table(MASK_SLOT)
        schema = writer.table_schema(table)
        provenance = writer.provenance()
        field = label_field_of(writer.table_schema(ENTITY_TABLE))
        view_ids = [medium["view_id"] for medium in result["media"]] + [view["view_id"] for view in result["skipped"]]
        boxes, entities = _prompting_boxes(writer.read, view_ids)
        outlined = _persons_masks(writer.read, view_ids)
        entities.update(
            _read_by_ids(
                writer.read,
                ENTITY_TABLE,
                {mask.entity_id for on_view in outlined.values() for mask in on_view} - entities.keys(),
            )
        )

        def class_of(entity_id: str) -> str:
            entity = entities.get(entity_id)
            return str(getattr(entity, field, "") or "") if entity is not None and field is not None else ""

        written = changed = left = 0
        for medium in result["media"]:
            current = {box.id: box for box in boxes[medium["view_id"]]}
            persons = outlined[medium["view_id"]]
            held = {mask.entity_id for mask in persons}
            protected = [(mask, class_of(mask.entity_id)) for mask in persons]
            rows = []
            for mask in medium["masks"]:
                box = current.get(mask["box_id"])
                if (
                    box is None
                    or box.entity_id != mask["entity_id"]
                    or pixel_prompt(box, medium["width"], medium["height"]) != mask["prompt"]
                ):
                    changed += 1
                    continue
                if box.entity_id in held or covered(
                    mask, class_of(box.entity_id), protected, params.overlap_threshold
                ):
                    left += 1
                    continue
                rows.append(
                    schema(
                        id="",
                        record_id=medium["record_id"],
                        view_id=medium["view_id"],
                        entity_id=box.entity_id,
                        size=mask["size"],
                        counts=mask["counts"],
                        **provenance,
                    )
                )
            written += len(writer.replace(table, medium["view_id"], rows))
        for view in result["skipped"]:
            writer.replace(table, view["view_id"], [])
        phases = result.get("phases_s", {})
        log.info(
            "job %s: phases read %.3f s, inference %.3f s, write %.3f s "
            "(%d mask(s), %d left to a person's mask, %d whose box changed)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("inference", 0.0),
            time.perf_counter() - started,
            written,
            left,
            changed,
        )

    @staticmethod
    def _segment(
        client: SyncPixanoInferenceClient, reference: str, prompts: list[list[int]], params: SegmentationParams
    ) -> Any:
        """One segmentation call, on one image, with all its boxes.

        One mask per box, said explicitly: the client asks for three by default. The predictor is
        reset, so the image is encoded anew: the server keeps one per replica, and another call —
        another chunk, a person's interactive segmentation — may have set another image since.
        """
        request = SegmentationRequest(
            model=params.model,
            image=reference,
            boxes=prompts,
            multimask_output=False,
            num_multimask_outputs=MASKS_PER_PROMPT,
            reset_predictor=True,
        )
        return client.segmentation(request, timeout=params.request_timeout_s).data


def _one_mask_per_prompt(output: Any, prompts: int, grid: list[int]) -> list[Any] | _Refusal:
    """The answer's mask for each box, in order, or why the answer does not fit the image.

    SAM 2 answers one mask per box even when asked about none, so the count is what tells an
    answer to the question from another. The size is checked here and not trusted to the
    schema, whose check lets any size through, and a mask on another grid would be drawn out of
    place. Uncompressed runs are not what Pixano stores: refused, like a string that does not
    fill its grid.
    """
    per_prompt = [len(per_box) for per_box in output.masks]
    if per_prompt != [MASKS_PER_PROMPT] * prompts:
        return _Refusal(WRONG_MASK_COUNT, {"boxes": prompts, "masks": per_prompt})
    masks = [per_box[0] for per_box in output.masks]
    for mask in masks:
        if list(mask.size) != grid:
            return _Refusal(MASK_SIZE_DIFFERS, {"image": grid, "mask": list(mask.size)})
        if not is_readable(mask):
            return _Refusal(UNREADABLE_MASK, {"size": list(mask.size)})
    return masks


def _text(counts: bytes | str) -> str:
    """A mask's compressed runs as text, which the dataset's schema reads back as bytes."""
    return counts.decode() if isinstance(counts, (bytes, bytearray)) else str(counts)


def _prompting_boxes(
    read: Callable[[str, str], list[Any]], view_ids: Sequence[str]
) -> tuple[defaultdict[str, list[Any]], dict[str, Any]]:
    """The boxes that prompt a mask on each view, by identifier, with the objects they name.

    A box prompts when it names an object that exists, whoever made it: a person's, or a model's,
    pending or accepted. Sorted by identifier, so that the masks of a rerun take the same ranks.
    """
    by_view: defaultdict[str, list[Any]] = defaultdict(list)
    if not view_ids:
        return by_view, {}
    boxes = [box for box in read(BBOX_TABLE, f"view_id IN {to_sql_list(list(view_ids))}") if box.entity_id]
    entities = _read_by_ids(read, ENTITY_TABLE, {box.entity_id for box in boxes})
    for box in sorted(boxes, key=lambda box: box.id):
        if box.entity_id in entities:
            by_view[box.view_id].append(box)
    return by_view, entities


def _persons_masks(read: Callable[[str, str], list[Any]], view_ids: Sequence[str]) -> defaultdict[str, list[Any]]:
    """The masks a person drew or accepted on each view, whatever their model.

    A model's mask nobody reviewed is no one's word: another model's pending mask never keeps
    this one from proposing its own.
    """
    by_view: defaultdict[str, list[Any]] = defaultdict(list)
    if not view_ids:
        return by_view
    for mask in read(MASK_TABLE, f"view_id IN {to_sql_list(list(view_ids))}"):
        if is_a_persons_work(mask):
            by_view[mask.view_id].append(mask)
    return by_view


def _read_by_ids(read: Callable[[str, str], list[Any]], table: str, ids: Iterable[str]) -> dict[str, Any]:
    """Rows of a table by identifier, a bounded number per filter."""
    return {row.id: row for batch in _batched(ids) for row in read(table, f"id IN {to_sql_list(batch)}")}


def _batched(ids: Iterable[str]) -> Iterator[list[str]]:
    """Identifiers in groups of at most `IDS_PER_READ`, in a stable order."""
    ordered = sorted(ids)
    for start in range(0, len(ordered), IDS_PER_READ):
        yield ordered[start : start + IDS_PER_READ]
