# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The tracking job kind: an object annotated on a video's frame, followed through the video by a model.

A tracking model — SAM 2's video predictor — takes frames and, for each object, a prompt on one of
them, and answers the object's mask on every later frame. The prompt is the object's annotation on
a frame, its keyframe: the mask, else the box, drawn there. The job follows the object from its
keyframe to the video's end, and proposes on each later frame, pending review, its mask, the box
around that mask, or both, as asked, with one tracklet spanning them.

A video is a view of a record, its frames a sequence: a record filmed by several cameras holds as
many videos, told apart by their logical name, and an object is followed in the video its keyframe
is in. A video is one chunk, and its tasks are its frames, which the progress counts: an object's
identity runs through the whole video, and a video cut across chunks would lose it. Its frames are
sent by windows, each one call short enough for the inference's limit; a window starts on the
previous one's last frame, prompted with the mask the model gave there, which carries each object
from one window to the next. Between two windows the chunk says how far it got, and stops if its
job was cancelled. Nothing is written before the video's end: an interrupted video is tracked
again from its start, and its rows, keyed by video and object, replace rather than double those of
the attempt before.

A person's work is never contradicted: a frame on which the object holds a mask someone drew or
accepted gets no model mask, one where it holds such a box no model box, and the keyframe's
annotation stays as it is. A track from a later frame replaces what the model proposed after that
frame only — and on it, when a person's annotation there prompts the track: what an earlier track
proposed before it stays.
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Sequence

import httpx
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_inference.schemas import CompressedRLE as PromptMask
from pixano_inference.schemas.tracking import TrackingBoxPrompt
from pixano_inference.schemas.v1 import TrackingKeyframeV1, TrackingPrompts, TrackingRequestV1
from pydantic import BaseModel, ConfigDict, Field

from pixano.inference.types import TASK_TO_CAPABILITY, InferenceTask
from pixano.schemas import NOT_REVIEWED_STATUSES, AnnotationSourceKind, ReviewStatus
from pixano.schemas.table_names import canonical_table_name_for_slot
from pixano.utils.python import to_sql_list

from ..reader import PAGE_SIZE, JobReader, MediaType
from ..writer import ENTITY_TABLE, MODEL_SOURCE, Coverage, JobWriter, ModelIdentity, is_a_persons_work
from .base import MODEL_TASK_MARKER, Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError
from .boxes import BOX_FORMAT
from .inference import REFUSED_BY_THE_SERVER, InferenceServer, chunk_media, classify, quarantined_item, refusal_detail
from .masks import is_empty, is_readable, normalized_bounds, pixel_prompt


log = logging.getLogger("pixano-worker")

# The task of the model this kind calls, in Pixano's vocabulary and in pixano-inference's.
TRACKING_TASK = InferenceTask.VIDEO_MASK_GENERATION
TRACKING_CAPABILITY = TASK_TO_CAPABILITY[TRACKING_TASK]

FRAME_TABLE = canonical_table_name_for_slot("sequence_frame")
MASK_SLOT = "mask"
MASK_TABLE = canonical_table_name_for_slot(MASK_SLOT)
BBOX_SLOT = "bbox"
BBOX_TABLE = canonical_table_name_for_slot(BBOX_SLOT)
TRACKLET_SLOT = "tracklet"

#: What the job proposes on each frame it follows an object to: the object's mask, the box around
#: that mask, or both.
Output = Literal["masks", "boxes", "both"]
#: Masks, all the job proposed before it could propose boxes: a job that does not ask proposes the same.
DEFAULT_OUTPUT: Output = "masks"
#: The tables each output writes into, by their slot.
OUTPUT_SLOTS: dict[str, tuple[str, ...]] = {
    "masks": (MASK_SLOT,),
    "boxes": (BBOX_SLOT,),
    "both": (MASK_SLOT, BBOX_SLOT),
}
#: Where a chunk's result holds an object's proposals for each table, by its slot.
RESULT_FIELDS = {MASK_SLOT: "masks", BBOX_SLOT: "boxes"}
#: The table of each slot the job proposes into.
TABLE_OF_SLOT = {MASK_SLOT: MASK_TABLE, BBOX_SLOT: BBOX_TABLE}

# Frames per call for one object. SAM 2.1 tiny's video predictor takes 15 to 29 s a frame through
# the compose's inference on CPU, as the machine is loaded (2 CPUs, measured 2026-11-05 and 06):
# sixteen frames keep a call between four and eight minutes. A GPU takes far larger windows.
DEFAULT_WINDOW = 16
MAX_WINDOW = 512
# Two frames at least: a window shares its first frame with the previous one.
MIN_WINDOW = 2
# No call is tried again at once. A replica answers one call at a time, and goes on computing a
# call the server timed out or whose client left: a retry would wait behind that computation, for
# minutes. A call that fails goes back to the queue with its chunk, after its delay.
DEFAULT_MAX_RETRIES = 0
MAX_RETRIES = 10
# The server gives a tracking call ten minutes by default, its time queued behind other calls
# included, then answers 504; the local stack gives it half an hour, for the calls a worker keeps
# in flight. A minute more here, so that the server's answer arrives before the client gives up.
DEFAULT_REQUEST_TIMEOUT_S = 1860.0

# A person's work, as a filter that narrows what is read: a row no model produced, or a model's row
# a person reviewed — every stored status but those of `NOT_REVIEWED_STATUSES`, as `is_reviewed`
# reads them. Positive comparisons only, which an index serves right (`TableQueryBuilder.
# force_full_scan`); `is_a_persons_work` decides on each row read.
PERSONS_WORK = (
    "(source_type IN "
    f"{to_sql_list(['', *(kind.value for kind in AnnotationSourceKind if kind.value != MODEL_SOURCE)])} "
    f"OR review_status IN "
    f"{to_sql_list([status.value for status in ReviewStatus if status.value not in NOT_REVIEWED_STATUSES])})"
)

# Why a video goes to quarantine, as its record in the queue says it.
FRAME_NOT_FOUND = "a frame of the video could not be found"

# Why a job is refused at planning.
NOT_A_VIDEO_DATASET = "this dataset has no video frames to track objects through"
NOTHING_TO_TRACK = "no object to track: annotate an object on a frame of a video first"
NO_FRAME_AFTER = "no frame comes after the keyframe of the objects to track"

#: An object in a video: its record, the video's logical name in it, and the object.
Track = tuple[str, str, str]


class TrackingTarget(BaseModel):
    """An object to track, as a person points at it.

    Attributes:
        record_id: The object's record.
        entity_id: The object.
        frame_index: The frame to start from, where the object is annotated — in each of the
            record's videos where it is, on that frame; None: the first frame where it is.
    """

    # A misspelt field would otherwise be dropped, and the track start from another frame.
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    frame_index: int | None = Field(default=None, ge=0)


class TrackingParams(JobParams):
    """Parameters of the tracking job.

    Attributes:
        model: The tracking model, as the inference declares it.
        media: The media types to run the model on: videos, as sequences of frames.
        objects: The objects to track. None given: every object a person annotated on a frame of
            a video, from the first frame where they did.
        output: What is proposed on each frame an object is followed to: its mask, the box around
            that mask, or both. Its mask by default (`DEFAULT_OUTPUT`).
        window: Frames per call to the inference, for one object followed: a call following
            several takes as many times fewer (`_frames_per_call`). A window shares its first
            frame with the previous one, which carries each object from one to the next.
        max_retries: Short retries of a call that failed transiently, done by the inference client
            before handing back; none by default (`DEFAULT_MAX_RETRIES`). Beyond that, the chunk
            is handed back to the queue.
        request_timeout_s: Beyond this, a call is considered lost.
    """

    model: str = Field(min_length=1, json_schema_extra={MODEL_TASK_MARKER: TRACKING_TASK.value})
    media: list[MediaType] = Field(default=["video"], min_length=1)
    objects: list[TrackingTarget] = Field(default=[])
    output: Output = Field(
        default=DEFAULT_OUTPUT,
        description="What the model proposes on each frame it follows an object to: the object's mask, "
        "the box around that mask, or both.",
    )
    window: int = Field(default=DEFAULT_WINDOW, ge=MIN_WINDOW, le=MAX_WINDOW)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0, le=MAX_RETRIES)
    request_timeout_s: float = Field(default=DEFAULT_REQUEST_TIMEOUT_S, gt=0)


@dataclass
class _Object:
    """An object of a video being tracked: where it starts, and what prompts it there."""

    entity_id: str
    track_id: int
    keyframe: int
    position: int
    prompt: TrackingPrompts | None = None
    # The prompt is a person's annotation: what the model proposed on the keyframe gives way to it.
    prompted_by_a_person: bool = False
    masks: dict[int, dict[str, Any]] = field(default_factory=dict)


class TrackingKind(JobKind[TrackingParams]):
    """Follows annotated objects through their videos, proposing their mask or box on each later frame for review."""

    name = "tracking"
    params_model = TrackingParams
    # A tracking model reads a video as its frames.
    supported_media = frozenset({"video"})
    # A mask or a box is the output of a model, and arrives pending review.
    source_type = MODEL_SOURCE

    #: How the engine runs the job, not what it computes, and the objects pointed at, which the
    #: rows name themselves: absent from the provenance.
    params_not_in_provenance = JobKind.params_not_in_provenance | {"request_timeout_s", "max_retries", "objects"}

    def __init__(self, inference_url: str = "", api_key: str = "") -> None:
        """Bind this kind to the inference server the worker knows."""
        self.server = InferenceServer(inference_url, api_key)

    def model_identity(self, params: TrackingParams) -> ModelIdentity:
        """The model's name, and the checkpoint the server loaded under it."""
        return self.server.model_identity(params.model)

    def prepare(self, writer: JobWriter, params: TrackingParams) -> None:
        """Give the dataset the tables of what the job writes, and of tracklets, where it has none.

        A video annotated with boxes only has no table of masks: one is added only when masks are
        asked for.
        """
        for slot in OUTPUT_SLOTS[params.output]:
            writer.ensure_table(slot)
        writer.ensure_table(TRACKLET_SLOT)

    def plan(self, reader: JobReader, params: TrackingParams) -> Iterable[Chunk]:
        """A chunk per video holding an object to track, from the earliest keyframe of its objects.

        Raises:
            ValueError: Videos cannot be processed, the dataset has no frames or objects, an object
                named cannot be tracked, nothing is left to track, or the inference serves no such
                model.
        """
        self.refuse_unsupported_media(params.media)
        tables = reader.dataset.info.tables
        if FRAME_TABLE not in tables:
            raise ValueError(NOT_A_VIDEO_DATASET)
        if ENTITY_TABLE not in tables:
            raise ValueError(NOTHING_TO_TRACK)
        self.server.require_served(params.model, TRACKING_CAPABILITY)
        keyframes = _named_keyframes(reader, params.objects) if params.objects else _persons_keyframes(reader)
        if not keyframes:
            raise ValueError(NOTHING_TO_TRACK)
        by_video: defaultdict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
        for (record_id, view, entity_id), keyframe in sorted(keyframes.items()):
            by_video[(record_id, view)].append((entity_id, keyframe))
        planned = False
        for (record_id, view), objects in sorted(by_video.items()):
            start = min(keyframe for _, keyframe in objects)
            frames = reader.count(FRAME_TABLE, f"{_of_video(record_id, view)} AND frame_index > {start}")
            if frames == 0:
                continue
            planned = True
            yield Chunk(
                payload={
                    "record_id": record_id,
                    "view": view,
                    "objects": [{"entity_id": entity_id, "frame_index": keyframe} for entity_id, keyframe in objects],
                },
                task_count=frames,
                # A call per window at most, each kept about as long as one of any kind is.
                weight=math.ceil(frames / (_frames_per_call(params.window, len(objects)) - 1)),
            )
        if not planned:
            raise ValueError(NO_FRAME_AFTER)

    def process(self, reader: JobReader, payload: dict[str, Any], params: TrackingParams) -> dict[str, Any]:
        """Track a video's objects window after window, and return their masks, the boxes around them, or both.

        The model answers masks, which carry each object from one window to the next whatever is
        asked for; the boxes are drawn around them once the video is tracked.

        A frame after the earliest keyframe is **produced** when an object got a mask on it,
        **skipped** when none did — every object lost, or not started yet. A video one of whose
        frames cannot be found, or that the inference refuses, goes to **quarantine** whole, its
        other frames skipped: an object cannot be carried across a missing frame.

        Raises:
            TransientError: The inference does not answer, or asks to come back later.
            ChunkCancelled: The job was cancelled meanwhile.
        """
        record_id: str = payload["record_id"]
        view: str = payload["view"]
        started = time.perf_counter()
        frames = sorted(reader.read(FRAME_TABLE, _of_video(record_id, view)), key=lambda frame: frame.frame_index)
        positions = {frame.frame_index: position for position, frame in enumerate(frames)}
        targets = [
            (target["entity_id"], target["frame_index"])
            for target in payload["objects"]
            if target["frame_index"] in positions
        ]
        objects = {
            entity_id: _Object(entity_id, track, keyframe, positions[keyframe])
            for track, (entity_id, keyframe) in enumerate(sorted(targets), start=1)
        }
        _prompt(reader, frames, objects)
        objects = {entity_id: target for entity_id, target in objects.items() if target.prompt is not None}
        result: dict[str, Any] = {
            "record_id": record_id,
            "view": view,
            "first_frame_id": frames[0].id if frames else "",
            "objects": [],
            # Every frame of the video, earlier ones included: a tracklet may span what an earlier
            # track proposed before this one's keyframe.
            "frames": {
                frame.frame_index: {"id": frame.id, "timestamp": float(getattr(frame, "timestamp", 0.0) or 0.0)}
                for frame in frames
            },
            "quarantined": [],
        }
        if not objects:
            return result
        start = min(target.position for target in objects.values())
        read_s = time.perf_counter() - started

        started = time.perf_counter()
        try:
            result["set_aside"] = self._track(reader, frames, objects, start, params)
        except _VideoRefused as refusal:
            result["quarantined"].append(
                quarantined_item(result["first_frame_id"], refusal.reason, record_id, view=view, **refusal.detail)
            )
            return result
        slots = OUTPUT_SLOTS[params.output]
        result["objects"] = [
            {
                "entity_id": target.entity_id,
                "keyframe": target.keyframe,
                "prompted_by_a_person": target.prompted_by_a_person,
                "masks": (
                    [{"frame_index": index, **mask} for index, mask in sorted(target.masks.items())]
                    if MASK_SLOT in slots
                    else []
                ),
                "boxes": _boxes_around(target.masks) if BBOX_SLOT in slots else [],
            }
            for target in objects.values()
        ]
        result["phases_s"] = {"read": read_s, "inference": time.perf_counter() - started}
        return result

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """The frames after the earliest keyframe: produced when an object got a mask or a box on one."""
        quarantined = [QuarantinedItem.model_validate(item) for item in result["quarantined"]]
        with_output = {
            proposal["frame_index"]
            for target in result["objects"]
            for proposal in (*target["masks"], *target["boxes"])
        }
        produced = min(len(with_output), task_count - len(quarantined))
        return Outcome(produced=produced, skipped=task_count - produced - len(quarantined), quarantined=quarantined)

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: TrackingParams
    ) -> None:
        """Write each object's masks, the boxes around them, or both, with the tracklet spanning them.

        Read again first, as `process` ran outside this worker's write lock of the dataset — through
        this worker's dataset, which sees what this worker wrote, not what a person saved meanwhile
        (backend-processing §18): an object deleted gets nothing, and its model rows go; a frame on
        which a person drew or accepted the object's mask gets no model mask, one on which they drew
        or accepted its box no model box. Only the model's rows after the keyframe are replaced — the
        keyframe's too when a person's annotation prompted the track, a correction of what the model
        proposed there —, in the tables this run writes into: a run asked for boxes leaves the masks
        an earlier run proposed, and the other way round — but an object deleted loses the model's
        masks and boxes alike. The tracklet spans every mask that names it, those an earlier track
        proposed before the keyframe and those a person accepted included, and every box this kind
        wrote that names it.
        """
        started = time.perf_counter()
        tables = {slot: writer.ensure_table(slot) for slot in OUTPUT_SLOTS[params.output]}
        tracklets_table = writer.ensure_table(TRACKLET_SLOT)
        schemas = {slot: writer.table_schema(table) for slot, table in tables.items()}
        tracklet_schema = writer.table_schema(tracklets_table)
        # The tables of masks and boxes the dataset holds, whatever this run writes: an earlier run's
        # rows of the other output name the object's tracklet too.
        held_slots = [slot for slot, table in TABLE_OF_SLOT.items() if table in writer.dataset.info.tables]
        # What names a tracklet, by table: every mask, as before boxes; a box only as this kind wrote
        # it. A person's box joined to the model's tracklet is left out, as a job asked for masks
        # always left it: counted, it would change what such a job writes.
        naming = {
            MASK_TABLE: "",
            BBOX_TABLE: f" AND source_name IN {to_sql_list([self.name])}",
        }
        provenance = writer.provenance()
        record_id, view, first_frame_id = result["record_id"], result["view"], result["first_frame_id"]
        frames = {int(index): frame for index, frame in result["frames"].items()}
        entity_ids = [target["entity_id"] for target in result["objects"]]
        present = (
            {row.id for row in writer.read(ENTITY_TABLE, f"id IN {to_sql_list(entity_ids)}")} if entity_ids else set()
        )
        frame_ids = {frame["id"] for frame in frames.values()}
        held = {slot: _persons_frames(writer.read, table, entity_ids, frame_ids) for slot, table in tables.items()}
        set_aside = result.get("set_aside", 0)

        def tracklet(entity_id: str, first: int, last: int) -> Any:
            return tracklet_schema(
                id="",
                record_id=record_id,
                view_id=first_frame_id,
                entity_id=entity_id,
                start_timestep=first,
                end_timestep=last,
                start_timestamp=frames[first]["timestamp"] if first in frames else 0.0,
                end_timestamp=frames[last]["timestamp"] if last in frames else 0.0,
                **provenance,
            )

        def annotation(slot: str, entity_id: str, tracklet_id: str, proposal: dict[str, Any]) -> Any:
            shape = (
                {"size": proposal["size"], "counts": proposal["counts"]}
                if slot == MASK_SLOT
                else {"coords": proposal["coords"], "format": BOX_FORMAT, "is_normalized": True}
            )
            return schemas[slot](
                id="",
                record_id=record_id,
                view_id=first_frame_id,
                entity_id=entity_id,
                tracklet_id=tracklet_id,
                frame_id=frames[proposal["frame_index"]]["id"],
                frame_index=proposal["frame_index"],
                **shape,
                **provenance,
            )

        written = dict.fromkeys(tables, 0)
        for target in result["objects"]:
            entity_id, keyframe = target["entity_id"], target["keyframe"]
            key = f"{record_id}:{view}:{entity_id}"
            tracklet_key = _keyed(key, TRACKLET_SLOT)
            if entity_id not in present:
                # Gone, whatever this run proposes: nothing will track it again to clean what is left.
                writer.replace(tracklets_table, tracklet_key, [])
                for slot in held_slots:
                    writer.replace(TABLE_OF_SLOT[slot], _keyed(key, slot), [])
                continue
            kept = {
                slot: [
                    proposal
                    for proposal in target[RESULT_FIELDS[slot]]
                    if proposal["frame_index"] in frames and proposal["frame_index"] not in held[slot][entity_id]
                ]
                for slot in tables
            }
            # Written first, so that the rows name it; its span is set once every row naming it is known.
            last_new = max(
                (proposal["frame_index"] for proposals in kept.values() for proposal in proposals), default=keyframe
            )
            [tracklet_id] = writer.replace(tracklets_table, tracklet_key, [tracklet(entity_id, keyframe, last_new)])
            replaced = _from(keyframe) if target["prompted_by_a_person"] else _after(keyframe)
            for slot, table in tables.items():
                rows = [annotation(slot, entity_id, tracklet_id, proposal) for proposal in kept[slot]]
                written[slot] += len(writer.replace(table, _keyed(key, slot), rows, covers=replaced))
            named = sorted(
                int(row.frame_index)
                for slot in held_slots
                for row in writer.read(
                    TABLE_OF_SLOT[slot],
                    f"entity_id IN {to_sql_list([entity_id])} AND tracklet_id IN {to_sql_list([tracklet_id])}"
                    f"{naming[TABLE_OF_SLOT[slot]]}",
                )
            )
            if not named:
                writer.replace(tracklets_table, tracklet_key, [])
            elif (min(keyframe, named[0]), named[-1]) != (keyframe, last_new):
                # The same rank, so the same identifier: the rows still name it.
                writer.replace(
                    tracklets_table, tracklet_key, [tracklet(entity_id, min(keyframe, named[0]), named[-1])]
                )
        phases = result.get("phases_s", {})
        log.info(
            "job %s: phases read %.3f s, inference %.3f s, write %.3f s "
            "(%d mask(s) and %d box(es) on %d object(s), %d mask(s) set aside: empty, unreadable or not the "
            "frame's size)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("inference", 0.0),
            time.perf_counter() - started,
            written.get(MASK_SLOT, 0),
            written.get(BBOX_SLOT, 0),
            len(result["objects"]),
            set_aside,
        )

    def _track(
        self,
        reader: JobReader,
        frames: Sequence[Any],
        objects: dict[str, "_Object"],
        start: int,
        params: TrackingParams,
    ) -> int:
        """Run the windows of a video, from its earliest keyframe to its end, filling each object's masks.

        Returns:
            How many masks the model answered were set aside: empty, unreadable, or not the size of
            their frame. Each leaves its object without a mask there, as an object lost would.

        Raises:
            _VideoRefused: A frame cannot be found, or the inference refuses the video.
            TransientError: The inference does not answer, or asks to come back later.
            ChunkCancelled: The job was cancelled between two windows.
        """
        by_track = {target.track_id: target for target in objects.values()}
        carried: dict[str, TrackingPrompts] = {}
        lost: set[str] = set()
        set_aside = 0
        position = start
        with self.server.client(max_retries=params.max_retries) as client:
            while position < len(frames) - 1:
                reach = min(position + params.window, len(frames))
                in_reach = [
                    target
                    for target in objects.values()
                    if target.entity_id not in lost
                    and (target.entity_id in carried or position <= target.position < reach)
                ]
                if not in_reach:
                    upcoming = [target.position for target in objects.values() if target.position >= reach]
                    if not upcoming:
                        break
                    position = min(upcoming)
                    continue
                end = min(position + _frames_per_call(params.window, len(in_reach)), len(frames))
                active = [target for target in in_reach if target.entity_id in carried or target.position < end]
                if not active:
                    # Every object in reach starts past the shorter window: on to the first of them.
                    position = min(target.position for target in in_reach)
                    continue
                window = frames[position:end]
                media = chunk_media(reader, FRAME_TABLE, [frame.id for frame in window])
                if media.quarantined:
                    raise _VideoRefused(FRAME_NOT_FOUND, {"frames": [item["item_id"] for item in media.quarantined]})
                keyframes = [
                    (target, 0, carried[target.entity_id])
                    if target.entity_id in carried
                    else (target, target.position - position, target.prompt)
                    for target in active
                ]
                output = _call(client, [reference for _, reference in media.media], keyframes, params)
                for tracked in output.frames:
                    at = position + tracked.frame_index
                    if not position <= at < end:
                        continue
                    frame = frames[at]
                    grid = [int(getattr(frame, "height", 0) or 0), int(getattr(frame, "width", 0) or 0)]
                    for answer in tracked.objects:
                        target = by_track.get(answer.track_id)
                        # Its keyframe holds the person's annotation; the window's first frame, a
                        # carried object's mask from the window before.
                        if target is None or at <= target.position or answer.mask is None:
                            continue
                        if target.entity_id in carried and at == position:
                            continue
                        mask = answer.mask
                        if (0 not in grid and list(mask.size) != grid) or not is_readable(mask) or is_empty(mask):
                            set_aside += 1
                            continue
                        target.masks[frame.frame_index] = {"size": list(mask.size), "counts": _text(mask.counts)}
                last = end - 1
                for target in active:
                    if target.position == last:
                        carried[target.entity_id] = target.prompt  # type: ignore[assignment]
                    elif (mask := target.masks.get(frames[last].frame_index)) is not None:
                        carried[target.entity_id] = TrackingPrompts(
                            mask=PromptMask(size=mask["size"], counts=mask["counts"])
                        )
                    elif target.position < last:
                        carried.pop(target.entity_id, None)
                        lost.add(target.entity_id)
                reader.progress.advance_to(last - start)
                reader.progress.stop_if_cancelled()
                position = last
        return set_aside


class _VideoRefused(Exception):
    """A video that cannot be tracked through: why, with what tells it."""

    def __init__(self, reason: str, detail: dict[str, Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _frames_per_call(window: int, objects: int) -> int:
    """The frames a call takes when it follows these objects: the window, shared out among them.

    Each object costs about as much as the frame itself, or more: SAM 2.1 tiny's video predictor
    took 15 s a frame for one object and 25 s for two, on the same six frames on CPU (measured
    2026-11-06). Shared out, a call takes about as long whatever it follows.
    """
    return max(MIN_WINDOW, window // max(objects, 1))


def _of_video(record_id: str, view: str) -> str:
    """The filter of a video's frames: a view of a record, which may hold several."""
    return f"record_id IN {to_sql_list([record_id])} AND logical_name IN {to_sql_list([view])}"


def _keyed(key: str, slot: str) -> str:
    """The key of an object's rows in a table: its own for the masks, the table's slot added for the others.

    A key's rows are numbered from zero in every table: keyed alike, the object's tracklet and its
    first box would share their identifier with its first mask, and the interface finds an
    annotation by its identifier, whatever its table. The masks keep the object's key, under which
    every run wrote them before the job could propose boxes, and which a rerun replaces.
    """
    return key if slot == MASK_SLOT else f"{key}:{slot}"


def _boxes_around(masks: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """The box around each of an object's masks, by frame, as the dataset stores a box: normalised `xywh`."""
    boxes = []
    for index, mask in sorted(masks.items()):
        corners = normalized_bounds(mask)
        if corners is None:
            continue
        left, top, right, bottom = corners
        boxes.append({"frame_index": index, "coords": [left, top, right - left, bottom - top]})
    return boxes


def _after(keyframe: int) -> Coverage:
    """The model's earlier masks or boxes a track from this keyframe replaces: those after it."""
    return lambda row, _: int(row.frame_index) > keyframe


def _from(keyframe: int) -> Coverage:
    """The model's earlier masks or boxes a track a person prompted replaces: those after it, and the one on it."""
    return lambda row, _: int(row.frame_index) >= keyframe


def _call(
    client: SyncPixanoInferenceClient,
    video: list[str],
    keyframes: list[tuple["_Object", int, TrackingPrompts | None]],
    params: TrackingParams,
) -> Any:
    """One tracking call on a window: each object prompted on its frame of the window, propagated to its end.

    Raises:
        _VideoRefused: The inference refuses the window.
        TransientError: The inference does not answer, or asks to come back later.
    """
    request = TrackingRequestV1(
        model=params.model,
        video=video,
        objects_ids=[target.track_id for target, _, _ in keyframes],
        frame_indexes=[frame for _, frame, _ in keyframes],
        keyframes=[TrackingKeyframeV1(frame_index=frame, prompts=prompt) for _, frame, prompt in keyframes],
        propagate=True,
    )
    try:
        return client.tracking(request, timeout=params.request_timeout_s).data
    except (httpx.TransportError, PixanoInferenceError) as error:
        failure = classify(error)
        if failure == "transient":
            raise TransientError(f"the inference does not answer or asks to come back later: {error}") from error
        if failure == "request":
            raise
        raise _VideoRefused(REFUSED_BY_THE_SERVER, refusal_detail(error)) from error  # type: ignore[arg-type]


def _prompt(reader: JobReader, frames: Sequence[Any], objects: dict[str, _Object]) -> None:
    """Give each object the prompt its keyframe holds: a person's annotation first, a mask before a box.

    A person's box drawn over what the model proposed on that frame — a drift corrected — prompts the
    track, not the model's mask. An annotation is on the video when its `view_id` is one of the
    video's frames, as planning reads it.
    """
    if not objects:
        return
    frame_at = {frame.frame_index: frame for frame in frames}
    frame_ids = {frame.id for frame in frames}
    keyframes = ", ".join(str(index) for index in sorted({target.keyframe for target in objects.values()}))
    where = f"entity_id IN {to_sql_list(list(objects))} AND frame_index IN ({keyframes})"
    tables = reader.dataset.info.tables
    candidates = [
        (table == BBOX_TABLE, row)
        for table in (MASK_TABLE, BBOX_TABLE)
        if table in tables
        for row in reader.read(table, where)
        if row.view_id in frame_ids
    ]
    for target in objects.values():
        frame = frame_at[target.keyframe]
        on_keyframe = [
            (is_box, row)
            for is_box, row in candidates
            if row.entity_id == target.entity_id and int(row.frame_index) == target.keyframe
        ]
        for is_box, row in sorted(
            on_keyframe, key=lambda candidate: (not is_a_persons_work(candidate[1]), candidate[0])
        ):
            prompt = _box_prompt(reader, frame, row) if is_box else _mask_prompt(row)
            if prompt is not None:
                target.prompt, target.prompted_by_a_person = prompt, is_a_persons_work(row)
                break


def _mask_prompt(mask: Any) -> TrackingPrompts | None:
    """A mask as a prompt; none for one that cannot be read or is empty."""
    if not is_readable(mask) or is_empty(mask):
        return None
    return TrackingPrompts(mask=PromptMask(size=list(mask.size), counts=_text(mask.counts)))


def _box_prompt(reader: JobReader, frame: Any, box: Any) -> TrackingPrompts | None:
    """A box as a prompt, in the frame's pixels; none when the frame's size is unknown or the box empty."""
    size = reader.image_size(FRAME_TABLE, frame)
    if size is None or (corners := pixel_prompt(box, *size)) is None:
        return None
    x1, y1, x2, y2 = corners
    return TrackingPrompts(box=TrackingBoxPrompt(x=x1, y=y1, width=x2 - x1, height=y2 - y1))


def _named_keyframes(reader: JobReader, targets: Sequence[TrackingTarget]) -> dict[Track, int]:
    """The keyframe of each object named, in each video of its record where it is: the frame given, else the first.

    The objects come from the caller: each is checked against the dataset's objects, read without a
    filter, before its identifier reaches one.

    Raises:
        ValueError: An object is not in the record named, or not annotated on the frame given.
    """
    known = set(reader.ids(ENTITY_TABLE))
    for target in targets:
        if target.entity_id not in known:
            raise ValueError(f"object '{target.entity_id}' is not in record '{target.record_id}'")
    entity_ids = sorted({target.entity_id for target in targets})
    entities = {row.id: row for row in reader.rows(ENTITY_TABLE, entity_ids)}
    for target in targets:
        entity = entities[target.entity_id]
        if entity.record_id != target.record_id:
            raise ValueError(f"object '{target.entity_id}' is not in record '{target.record_id}'")
    where = f"entity_id IN {to_sql_list(entity_ids)}"
    # Each object pointed at on a frame: only that frame's annotations are read.
    if all(target.frame_index is not None for target in targets):
        given = sorted({target.frame_index for target in targets if target.frame_index is not None})
        where += f" AND frame_index IN ({', '.join(str(index) for index in given)})"
    annotated = _annotated_frames(reader, where, lambda _: True)
    keyframes: dict[Track, int] = {}
    for target in targets:
        videos = {
            view: frames
            for (record_id, view, entity_id), frames in annotated.items()
            if record_id == target.record_id and entity_id == target.entity_id
        }
        if target.frame_index is None:
            starts = {view: min(frames) for view, frames in videos.items()}
            missing = f"object '{target.entity_id}' has no mask nor box on a frame to start from"
        else:
            starts = {view: target.frame_index for view, frames in videos.items() if target.frame_index in frames}
            missing = f"object '{target.entity_id}' has no mask nor box on frame {target.frame_index} to start from"
        if not starts:
            raise ValueError(missing)
        for view, keyframe in starts.items():
            keyframes[(target.record_id, view, target.entity_id)] = keyframe
    return keyframes


def _persons_keyframes(reader: JobReader) -> dict[Track, int]:
    """The first frame on which a person annotated each object of the dataset's videos, in each video."""
    annotated = _annotated_frames(reader, PERSONS_WORK, is_a_persons_work)
    return {track: min(frames) for track, frames in annotated.items()}


def _annotated_frames(reader: JobReader, where: str, keep: Callable[[Any], bool]) -> dict[Track, set[int]]:
    """The frames on which objects hold a mask or a box, by object and video.

    An annotation names its video by `view_id`, one of the video's frames — its first frame as both
    interfaces write it, the annotation's own frame for some imports —, and its frame by
    `frame_index`: one whose view is no frame of a video starts nothing. Read in one pass: a filter
    by pages would read every matching row again for each page (`TableQueryBuilder`), and what is
    read is bounded by the filter — a person's work, or the objects named.
    """
    tables = reader.dataset.info.tables
    found: list[tuple[str, str, str, int]] = []
    for table in (MASK_TABLE, BBOX_TABLE):
        if table not in tables:
            continue
        for row in reader.read(table, f"{where} AND frame_index >= 0"):
            if row.entity_id and row.view_id and keep(row):
                found.append((row.record_id, row.view_id, row.entity_id, int(row.frame_index)))
    views = _video_names(reader, sorted({view_id for _, view_id, _, _ in found}))
    annotated: defaultdict[Track, set[int]] = defaultdict(set)
    for record_id, view_id, entity_id, frame_index in found:
        if view_id in views:
            annotated[(record_id, views[view_id], entity_id)].add(frame_index)
    return annotated


def _video_names(reader: JobReader, view_ids: Sequence[str]) -> dict[str, str]:
    """The logical name of the video each of these frames is in: the frames table holds every camera's."""
    names: dict[str, str] = {}
    for offset in range(0, len(view_ids), PAGE_SIZE):
        for frame in reader.rows(FRAME_TABLE, view_ids[offset : offset + PAGE_SIZE]):
            names[frame.id] = frame.logical_name
    return names


def _persons_frames(
    read: Any, table: str, entity_ids: Sequence[str], frame_ids: set[str]
) -> defaultdict[str, set[int]]:
    """The frames of the video on which a person drew or accepted each object's annotation in this table.

    No model annotation goes there in the same table: no model mask where a person's mask is, no
    model box where a person's box is.
    """
    held: defaultdict[str, set[int]] = defaultdict(set)
    if not entity_ids:
        return held
    for annotation in read(table, f"entity_id IN {to_sql_list(list(entity_ids))} AND {PERSONS_WORK}"):
        if is_a_persons_work(annotation) and annotation.view_id in frame_ids:
            held[annotation.entity_id].add(int(annotation.frame_index))
    return held


def _text(counts: bytes | str) -> str:
    """A mask's compressed runs as text, which the dataset's schema reads back as bytes."""
    return counts.decode() if isinstance(counts, (bytes, bytearray)) else str(counts)
