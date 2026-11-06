# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The tracking kind: which objects it follows from which frame, how it carries them from one window to
the next, and what it writes, leaving a person's work alone.

The dataset is a real one, read and written through the runner's own reader and writer; only the
inference is a stand-in. It answers each prompted object with a car that moves right by a few pixels a
frame, so that a mask says which frame it was drawn on.
"""

import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from PIL import Image as PILImage
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_worker import runner
from pixano_worker.kinds import MODEL_TASK_MARKER, TrackingKind, TransientError
from pixano_worker.kinds.inference import REFUSED_BY_THE_SERVER
from pixano_worker.kinds.tracking import (
    FRAME_NOT_FOUND,
    NO_FRAME_AFTER,
    NOT_A_VIDEO_DATASET,
    NOTHING_TO_TRACK,
    PERSONS_WORK,
    TRACKING_CAPABILITY,
    TrackingParams,
    _frames_per_call,
)
from pixano_worker.media import MediaResolver
from pixano_worker.progress import ChunkCancelled, ChunkProgress
from pycocotools import mask as mask_api

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import (
    NOT_REVIEWED_STATUSES,
    BBox,
    CompressedRLE,
    Entity,
    Image,
    Record,
    ReviewStatus,
    SequenceFrame,
    Tracklet,
)


DATASET_ID = "traffic"
WIDTH, HEIGHT = 200, 100
MODEL = "sam2.1-tiny-video"
INFERENCE_MEDIA_ROOT = "/inference-media"
# The video: seven frames of record r1, three of record r2.
FRAMES = {"r1": 7, "r2": 3}
# Record r1 is also filmed from behind: a second video of five frames, in the same frames table.
VIDEO, BACK = "video", "back"
BACK_FRAMES = 5
# The car on frame 0, in pixels: left, top, right, bottom. It moves right by STEP pixels a frame.
CAR_PX = (20, 30, 60, 70)
STEP = 10


def _car(frame_index: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = CAR_PX
    return left + STEP * frame_index, top, right + STEP * frame_index, bottom


def _rle(corners: tuple[int, int, int, int]) -> dict[str, Any]:
    left, top, right, bottom = corners
    pixels = np.zeros((HEIGHT, WIDTH), dtype=np.uint8, order="F")
    pixels[top:bottom, left:right] = 1
    encoded = mask_api.encode(pixels)
    return {"size": list(encoded["size"]), "counts": encoded["counts"]}


def _left_of(mask: Any) -> int:
    """Where a stored mask starts, in pixels: says the frame the stand-in drew it for."""
    x, _, _, _ = mask_api.toBbox({"size": list(mask.size), "counts": mask.counts})
    return int(x)


class _Inference:
    """A tracking model: each prompted object answered on every frame of the window from its prompt on."""

    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.lost_after: int | None = None
        # The frame after which one object, by its track, is lost; the others go on.
        self.lost_after_for: dict[int, int] = {}
        # SAM 2 answers every object from the window's first frame, before its prompt too.
        self.from_the_first_frame = False
        self.status: int | None = None
        self.on_call: Any = None

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        pass

    def list_models(self) -> list[Any]:
        return [SimpleNamespace(name=MODEL, model_path="facebook/sam2.1-hiera-tiny", capability=TRACKING_CAPABILITY)]

    def tracking(self, request: Any, **_kwargs: Any) -> Any:
        self.calls.append(request)
        if self.on_call is not None:
            self.on_call(len(self.calls))
        if self.status is not None:
            raise PixanoInferenceError(self.status, "error", "refused")
        # Each frame is a file named after its index: the window's frames, in order.
        indexes = [int(Path(str(reference)).stem.rsplit("-", 1)[-1]) for reference in request.video]
        frames = []
        for relative, index in enumerate(indexes):
            objects = []
            for track_id, prompted_at in zip(request.objects_ids, request.frame_indexes, strict=True):
                if relative < prompted_at and not self.from_the_first_frame:
                    continue
                lost_after = self.lost_after_for.get(track_id, self.lost_after)
                lost = lost_after is not None and index > lost_after
                corners = (0, 0, 0, 0) if lost else _car(index)
                objects.append(SimpleNamespace(track_id=track_id, mask=SimpleNamespace(**_rle(corners))))
            frames.append(SimpleNamespace(frame_index=relative, objects=objects))
        return SimpleNamespace(data=SimpleNamespace(frames=frames))


@dataclass
class _Scene:
    library: Path
    media: MediaResolver
    inference: _Inference
    kind: TrackingKind

    def dataset(self) -> Dataset:
        return Dataset.find(DATASET_ID, self.library)

    def plan(self, params: TrackingParams) -> list[Any]:
        return runner._plan_and_prepare(
            self.kind, self.library, DATASET_ID, self.media, "job-1", params, threading.Event()
        )

    def run(self, params: TrackingParams, job_id: str = "job-1", progress: ChunkProgress | None = None) -> list[Any]:
        """Plan, process and write every chunk as the runner does; the outcomes."""
        outcomes = []
        for chunk in self.plan(params):
            reader = runner._reader_for(
                self.library, DATASET_ID, self.media, progress=progress or ChunkProgress(chunk.task_count)
            )
            result = self.kind.process(reader, chunk.payload, params)
            outcomes.append(self.kind.outcome(result, chunk.payload, chunk.task_count))
            self.kind.write(
                runner._writer_for(self.library, DATASET_ID, self.kind, job_id, params), result, chunk.payload, params
            )
        return outcomes

    def masks(self, entity_id: str = "car") -> list[Any]:
        rows = self.dataset().get_data("masks", where=f"entity_id = '{entity_id}'")
        return sorted(rows, key=lambda row: row.frame_index)


def _frame_id(record_id: str, index: int, view: str = VIDEO) -> str:
    return f"{record_id}-f{index}" if view == VIDEO else f"{record_id}-{view}-f{index}"


def _frame(media_root: Path, record_id: str, index: int, view: str = VIDEO) -> SequenceFrame:
    file_name = f"{record_id}-{index}.png" if view == VIDEO else f"{record_id}-{view}-{index}.png"
    PILImage.new("RGB", (WIDTH, HEIGHT)).save(media_root / file_name)
    return SequenceFrame(
        id=_frame_id(record_id, index, view),
        record_id=record_id,
        logical_name=view,
        uri=str(media_root / file_name),
        width=WIDTH,
        height=HEIGHT,
        frame_index=index,
        timestamp=index / 10,
    )


@pytest.fixture
def scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Scene:
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(
            id=DATASET_ID,
            name="Traffic",
            record=Record,
            entity=Entity,
            bbox=BBox,
            mask=CompressedRLE,
            # A dataset that holds tracklets already: the job adds no table, and reads through the
            # worker's dataset as it opened it.
            tracklet=Tracklet,
            views={VIDEO: SequenceFrame, BACK: SequenceFrame},
        ),
    )
    dataset.add_records({"records": [Record(id=record_id) for record_id in FRAMES]})
    frames = [_frame(media_root, record_id, index) for record_id, count in FRAMES.items() for index in range(count)]
    frames += [_frame(media_root, "r1", index, BACK) for index in range(BACK_FRAMES)]
    dataset.add_data("sequence_frames", frames, raise_or_warn="none")
    inference = _Inference()
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", inference.client)
    return _Scene(
        library, MediaResolver(str(media_root), INFERENCE_MEDIA_ROOT), inference, TrackingKind("http://inference")
    )


def _annotate(
    scene: _Scene,
    entity_id: str = "car",
    record_id: str = "r1",
    frame_index: int = 0,
    *,
    source_type: str = "human",
    review_status: str = "",
    as_mask: bool = False,
    view: str = VIDEO,
) -> None:
    """An object, and its box — or mask — on a frame of one of its record's videos."""
    dataset = scene.dataset()
    if not dataset.get_data("entities", ids=[entity_id]):
        dataset.add_data("entities", [Entity(id=entity_id, record_id=record_id)])
    common = {
        "record_id": record_id,
        "entity_id": entity_id,
        "view_id": _frame_id(record_id, 0, view),
        "frame_id": _frame_id(record_id, frame_index, view),
        "frame_index": frame_index,
        "source_type": source_type,
        "review_status": review_status,
    }
    suffix = f"{frame_index}" if view == VIDEO else f"{view}-{frame_index}"
    if as_mask:
        dataset.add_data("masks", [CompressedRLE(id=f"m-{entity_id}-{suffix}", **_rle(_car(frame_index)), **common)])
        return
    left, top, right, bottom = _car(frame_index)
    coords = [left / WIDTH, top / HEIGHT, (right - left) / WIDTH, (bottom - top) / HEIGHT]
    dataset.add_data(
        "bboxes",
        [BBox(id=f"b-{entity_id}-{suffix}", coords=coords, format="xywh", is_normalized=True, **common)],
    )


def _params(**fields: Any) -> TrackingParams:
    fields.setdefault("window", 3)
    return TrackingParams(model=MODEL, **fields)


def _target(entity_id: str = "car", record_id: str = "r1", frame_index: int | None = 0) -> dict[str, Any]:
    return {"record_id": record_id, "entity_id": entity_id, "frame_index": frame_index}


class TestParams:
    def test_the_model_is_offered_among_the_tracking_ones(self) -> None:
        schema = TrackingParams.model_json_schema()

        assert schema["properties"]["model"][MODEL_TASK_MARKER] == "video_mask_generation"
        assert schema["properties"]["media"]["default"] == ["video"]

    def test_a_persons_work_is_read_whatever_status_a_review_leaves(self) -> None:
        # The filter narrows what `is_a_persons_work` decides on: it must keep every reviewed status.
        reviewed = [status.value for status in ReviewStatus if status.value not in NOT_REVIEWED_STATUSES]
        assert reviewed and all(f"'{status}'" in PERSONS_WORK for status in reviewed)

    def test_an_object_named_with_a_misspelt_field_is_refused(self) -> None:
        # Dropped instead, the frame would be lost and the track start from another one.
        with pytest.raises(ValueError, match="frameIndex"):
            _params(objects=[{"record_id": "r1", "entity_id": "car", "frameIndex": 3}])

    @pytest.mark.parametrize(
        "objects, frames",
        [(1, 16), (2, 8), (3, 5), (16, 2), (40, 2), (0, 16)],
        ids=["one", "two", "three", "as many as frames", "more", "none"],
    )
    def test_a_call_takes_fewer_frames_the_more_objects_it_follows(self, objects: int, frames: int) -> None:
        assert _frames_per_call(16, objects) == frames


class TestPlan:
    def test_a_chunk_per_video_from_its_earliest_keyframe_with_a_frame_per_task(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 2)
        _annotate(scene, "van", "r1", 4)
        _annotate(scene, "bus", "r2", 0)

        chunks = scene.plan(
            _params(objects=[_target("car", "r1", 2), _target("van", "r1", 4), _target("bus", "r2", 0)])
        )

        assert [(chunk.payload["record_id"], chunk.payload["view"], chunk.task_count) for chunk in chunks] == [
            ("r1", VIDEO, 4),
            ("r2", VIDEO, 2),
        ]
        assert chunks[0].payload["objects"] == [
            {"entity_id": "car", "frame_index": 2},
            {"entity_id": "van", "frame_index": 4},
        ]

    def test_a_video_weighs_the_calls_it_takes(self, scene: _Scene) -> None:
        _annotate(scene)

        [chunk] = scene.plan(_params(objects=[_target()], window=3))

        # Six frames after the keyframe, two new frames a window: three calls.
        assert chunk.weight == 3

    def test_a_video_of_several_objects_weighs_the_shorter_calls_it_takes(self, scene: _Scene) -> None:
        _annotate(scene, "car")
        _annotate(scene, "van")

        [chunk] = scene.plan(_params(objects=[_target("car"), _target("van")], window=4))

        # Two objects: two frames a call, one of them new: six calls for six frames.
        assert chunk.weight == 6

    def test_an_object_named_without_a_frame_starts_where_it_is_first_annotated(self, scene: _Scene) -> None:
        _annotate(scene, frame_index=3)
        _annotate(scene, frame_index=5)

        [chunk] = scene.plan(_params(objects=[_target(frame_index=None)]))

        assert chunk.payload["objects"] == [{"entity_id": "car", "frame_index": 3}]

    def test_with_none_named_every_object_a_person_annotated(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 1)
        _annotate(scene, "proposed", "r1", 0, source_type="model", review_status="pending")
        _annotate(scene, "accepted", "r2", 0, source_type="model", review_status="accepted")

        chunks = scene.plan(_params())

        assert [chunk.payload for chunk in chunks] == [
            {"record_id": "r1", "view": VIDEO, "objects": [{"entity_id": "car", "frame_index": 1}]},
            {"record_id": "r2", "view": VIDEO, "objects": [{"entity_id": "accepted", "frame_index": 0}]},
        ]

    @pytest.mark.parametrize(
        "target, refusal",
        [
            (_target("car", "r2", 0), "is not in record"),
            (_target("car", "r1", 4), "has no mask nor box on frame 4"),
            (_target("ghost", "r1", 0), "is not in record"),
        ],
        ids=["another record", "a frame it is not annotated on", "an object that does not exist"],
    )
    def test_an_object_named_wrong_is_refused(self, scene: _Scene, target: dict[str, Any], refusal: str) -> None:
        _annotate(scene)

        with pytest.raises(ValueError, match=refusal):
            scene.plan(_params(objects=[target]))

    def test_nothing_to_track_is_refused(self, scene: _Scene) -> None:
        _annotate(scene, "proposed", source_type="model", review_status="pending")

        with pytest.raises(ValueError, match=NOTHING_TO_TRACK):
            scene.plan(_params())

    def test_a_keyframe_on_the_last_frame_leaves_nothing_after_it(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r2", 2)

        with pytest.raises(ValueError, match=NO_FRAME_AFTER):
            scene.plan(_params(objects=[_target("car", "r2", 2)]))

    def test_a_dataset_of_images_is_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
        library = tmp_path / "images"
        Dataset.create(
            library / DATASET_ID, DatasetInfo(id=DATASET_ID, name="Images", record=Record, views={"image": Image})
        )
        kind = TrackingKind("http://inference")
        monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", _Inference().client)

        with pytest.raises(ValueError, match=NOT_A_VIDEO_DATASET):
            runner._plan_and_prepare(
                kind, library, DATASET_ID, MediaResolver.unconfigured(), "job-1", _params(), threading.Event()
            )


class TestTrack:
    def test_windows_share_a_frame_and_carry_each_object_by_its_last_mask(self, scene: _Scene) -> None:
        _annotate(scene)

        scene.run(_params(objects=[_target()], window=3))

        calls = scene.inference.calls
        assert [[Path(str(frame)).stem for frame in call.video] for call in calls] == [
            ["r1-0", "r1-1", "r1-2"],
            ["r1-2", "r1-3", "r1-4"],
            ["r1-4", "r1-5", "r1-6"],
        ]
        first, second = calls[0].keyframes[0].prompts, calls[1].keyframes[0].prompts
        assert first.box is not None and first.mask is None
        # The second window starts on frame 2, prompted with the mask the first gave there.
        assert second.mask is not None and _left_of(second.mask) == _car(2)[0]

    def test_a_mask_on_each_frame_after_the_keyframe_and_none_on_it(self, scene: _Scene) -> None:
        _annotate(scene)

        [outcome] = scene.run(_params(objects=[_target()]))

        masks = scene.masks()
        assert [(mask.frame_index, _left_of(mask)) for mask in masks] == [
            (index, _car(index)[0]) for index in range(1, 7)
        ]
        assert (outcome.produced, outcome.skipped) == (6, 0)

    def test_the_masks_sit_on_their_frames_of_the_video_pending_review(self, scene: _Scene) -> None:
        _annotate(scene)

        scene.run(_params(objects=[_target()]))

        mask = scene.masks()[0]
        assert (mask.view_id, mask.frame_id, mask.record_id) == (_frame_id("r1", 0), _frame_id("r1", 1), "r1")
        assert (mask.source_type, mask.source_name, mask.review_status) == ("model", "tracking", "pending")
        # The object pointed at is the row's own: not copied into its provenance.
        assert "objects" not in json.loads(mask.source_metadata)["params"]

    def test_one_tracklet_spans_the_keyframe_to_the_last_mask(self, scene: _Scene) -> None:
        _annotate(scene, frame_index=2)

        scene.run(_params(objects=[_target(frame_index=2)]))

        [tracklet] = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        assert (tracklet.start_timestep, tracklet.end_timestep) == (2, 6)
        assert (tracklet.start_timestamp, tracklet.end_timestamp) == pytest.approx((0.2, 0.6))
        assert {mask.tracklet_id for mask in scene.masks()} == {tracklet.id}

    def test_a_mask_of_the_keyframe_prompts_before_a_box(self, scene: _Scene) -> None:
        _annotate(scene)
        _annotate(scene, as_mask=True)

        scene.run(_params(objects=[_target()]))

        prompts = scene.inference.calls[0].keyframes[0].prompts
        assert prompts.mask is not None and prompts.box is None

    def test_the_box_prompt_is_in_pixels(self, scene: _Scene) -> None:
        _annotate(scene)

        scene.run(_params(objects=[_target()]))

        box = scene.inference.calls[0].keyframes[0].prompts.box
        assert (box.x, box.y, box.width, box.height) == (20, 30, 40, 40)

    def test_an_object_starting_later_joins_on_its_window(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 0)
        _annotate(scene, "van", "r1", 3)

        scene.run(_params(objects=[_target("car", "r1", 0), _target("van", "r1", 3)], window=3))

        calls = scene.inference.calls
        # The van's keyframe, frame 3, is in the second window: prompted there, on its own frame. Two
        # objects from then on, so two frames a call.
        assert [len(call.objects_ids) for call in calls] == [1, 2, 2, 2, 2]
        assert calls[1].frame_indexes == [0, 1]
        assert [mask.frame_index for mask in scene.masks("van")] == [4, 5, 6]
        assert [mask.frame_index for mask in scene.masks("car")] == [1, 2, 3, 4, 5, 6]

    def test_a_mask_answered_before_an_objects_keyframe_is_dropped(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 0)
        _annotate(scene, "van", "r1", 3)
        scene.inference.from_the_first_frame = True

        scene.run(_params(objects=[_target("car", "r1", 0), _target("van", "r1", 3)], window=3))

        assert [mask.frame_index for mask in scene.masks("van")] == [4, 5, 6]

    def test_a_stretch_no_object_is_followed_in_is_skipped_to_the_next_keyframe(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 0)
        _annotate(scene, "van", "r1", 5)
        # The car, track 1, is lost after frame 1: nothing is followed from frame 2 until the van's.
        scene.inference.lost_after_for = {1: 1}

        scene.run(_params(objects=[_target("car", "r1", 0), _target("van", "r1", 5)], window=3))

        assert [[Path(str(frame)).stem for frame in call.video] for call in scene.inference.calls] == [
            ["r1-0", "r1-1", "r1-2"],
            ["r1-5", "r1-6"],
        ]
        assert [mask.frame_index for mask in scene.masks("car")] == [1]
        assert [mask.frame_index for mask in scene.masks("van")] == [6]

    def test_an_object_lost_is_carried_no_further(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.inference.lost_after = 2

        [outcome] = scene.run(_params(objects=[_target()], window=3))

        assert [mask.frame_index for mask in scene.masks()] == [1, 2]
        assert len(scene.inference.calls) == 2
        assert (outcome.produced, outcome.skipped) == (2, 4)

    def test_progress_counts_the_frames_each_window_took(self, scene: _Scene) -> None:
        _annotate(scene)
        progress = ChunkProgress(6)
        seen: list[int] = []
        scene.inference.on_call = lambda _call: seen.append(progress.done)

        scene.run(_params(objects=[_target()], window=3), progress=progress)

        assert (seen, progress.done) == ([0, 2, 4], 6)

    def test_a_cancellation_stops_the_video_between_two_windows_and_writes_nothing(self, scene: _Scene) -> None:
        _annotate(scene)
        progress = ChunkProgress(6)
        scene.inference.on_call = lambda call: progress.cancel() if call == 1 else None

        with pytest.raises(ChunkCancelled):
            scene.run(_params(objects=[_target()], window=3), progress=progress)

        assert len(scene.inference.calls) == 1
        assert scene.masks() == []


class TestFailures:
    def test_a_frame_out_of_reach_sends_the_video_to_quarantine(self, scene: _Scene) -> None:
        _annotate(scene)
        dataset = scene.dataset()
        [frame] = dataset.get_data("sequence_frames", ids=[_frame_id("r1", 4)])
        frame.uri = ""
        dataset.update_data("sequence_frames", [frame])

        [outcome] = scene.run(_params(objects=[_target()], window=3))

        # The video, named by its first frame as its annotations name it, its record and camera beside.
        [item] = outcome.quarantined
        assert (item.item_id, item.reason) == (_frame_id("r1", 0), FRAME_NOT_FOUND)
        assert (item.detail or {})["record_id"] == "r1" and (item.detail or {})["view"] == VIDEO
        assert (outcome.produced, outcome.skipped) == (0, 5)
        assert scene.masks() == []

    def test_a_refusal_sends_the_video_to_quarantine(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.inference.status = 500

        [outcome] = scene.run(_params(objects=[_target()]))

        assert [item.reason for item in outcome.quarantined] == [REFUSED_BY_THE_SERVER]

    def test_an_inference_that_does_not_answer_hands_the_chunk_back(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.inference.status = 503

        with pytest.raises(TransientError):
            scene.run(_params(objects=[_target()]))

    def test_a_call_the_server_timed_out_is_not_sent_again_at_once(
        self, scene: _Scene, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The replica goes on computing a call it timed out: a call sent again at once would only wait
        # behind it. The chunk goes back to the queue instead — through the real client's retries.
        _annotate(scene)
        params = _params(objects=[_target()])
        [chunk] = scene.plan(params)
        sent: list[str] = []

        def timed_out(_client: httpx.Client, method: str, url: Any, **_kwargs: Any) -> httpx.Response:
            sent.append(method)
            return httpx.Response(
                504, json={"detail": "Inference timed out after 600s."}, request=httpx.Request(method, url)
            )

        monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", SyncPixanoInferenceClient)
        monkeypatch.setattr(httpx.Client, "request", timed_out)
        reader = runner._reader_for(scene.library, DATASET_ID, scene.media, progress=ChunkProgress(chunk.task_count))

        with pytest.raises(TransientError):
            scene.kind.process(reader, chunk.payload, params)

        assert sent == ["POST"]


class TestWrite:
    def test_a_rerun_replaces_the_masks_rather_than_doubling_them(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.run(_params(objects=[_target()]))
        first = [mask.id for mask in scene.masks()]

        scene.run(_params(objects=[_target()]), job_id="job-2")

        assert [mask.id for mask in scene.masks()] == first
        assert len(scene.dataset().get_data("tracklets", where="entity_id = 'car'")) == 1

    def test_no_tracklet_shares_its_identifier_with_a_mask(self, scene: _Scene) -> None:
        # The interface finds an annotation by its identifier, whatever its table.
        _annotate(scene)

        scene.run(_params(objects=[_target()]))

        [tracklet] = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        masks = scene.masks()
        assert masks and tracklet.id not in {mask.id for mask in masks}
        assert {mask.tracklet_id for mask in masks} == {tracklet.id}

    def test_a_frame_holding_a_persons_mask_gets_no_model_mask(self, scene: _Scene) -> None:
        _annotate(scene)
        _annotate(scene, frame_index=4, as_mask=True)

        scene.run(_params(objects=[_target()]))

        on_frame_4 = [mask for mask in scene.masks() if mask.frame_index == 4]
        assert [(mask.id, mask.source_type) for mask in on_frame_4] == [("m-car-4", "human")]

    def test_a_mask_a_person_accepted_stays_and_is_not_doubled(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.run(_params(objects=[_target()]))
        accepted = next(mask for mask in scene.masks() if mask.frame_index == 3)
        accepted.review_status = "accepted"
        scene.dataset().update_data("masks", [accepted])

        scene.run(_params(objects=[_target()]), job_id="job-2")

        on_frame_3 = [mask for mask in scene.masks() if mask.frame_index == 3]
        assert [(mask.id, mask.review_status) for mask in on_frame_3] == [(accepted.id, "accepted")]
        assert len(scene.masks()) == 6

    def test_an_object_deleted_meanwhile_gets_nothing(self, scene: _Scene) -> None:
        _annotate(scene)
        params = _params(objects=[_target()])
        [chunk] = scene.plan(params)
        reader = runner._reader_for(scene.library, DATASET_ID, scene.media, progress=ChunkProgress(chunk.task_count))
        result = scene.kind.process(reader, chunk.payload, params)
        # Deleted through the worker's own dataset: `write` sees what this worker wrote, not what
        # a person saved through the application meanwhile (backend-processing §18).
        runner._open_dataset(scene.library, DATASET_ID).delete_data("entities", ["car"])

        scene.kind.write(
            runner._writer_for(scene.library, DATASET_ID, scene.kind, "job-1", params), result, chunk.payload, params
        )

        assert scene.masks() == []
        assert scene.dataset().get_data("tracklets", where="entity_id = 'car'") == []


class TestVideos:
    def test_an_object_is_followed_in_the_video_its_keyframe_is_in(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 2, view=BACK)

        [chunk] = scene.plan(_params(objects=[_target("car", "r1", 2)]))
        scene.run(_params(objects=[_target("car", "r1", 2)]))

        assert (chunk.payload["view"], chunk.task_count) == (BACK, BACK_FRAMES - 3)
        sent = {Path(str(frame)).stem for call in scene.inference.calls for frame in call.video}
        assert sent == {f"r1-{BACK}-{index}" for index in range(2, BACK_FRAMES)}
        assert [(mask.frame_id, mask.view_id) for mask in scene.masks()] == [
            (_frame_id("r1", index, BACK), _frame_id("r1", 0, BACK)) for index in range(3, BACK_FRAMES)
        ]

    def test_an_object_drawn_in_two_videos_is_followed_in_each(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 1)
        _annotate(scene, "car", "r1", 1, view=BACK)

        chunks = scene.plan(_params(objects=[_target("car", "r1", 1)]))
        scene.run(_params(objects=[_target("car", "r1", 1)]))

        assert sorted(chunk.payload["view"] for chunk in chunks) == [BACK, VIDEO]
        masks = scene.masks()
        assert sorted(mask.frame_id for mask in masks) == sorted(
            [_frame_id("r1", index) for index in range(2, 7)] + [_frame_id("r1", index, BACK) for index in range(2, 5)]
        )
        tracklets = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        assert sorted((tracklet.view_id, tracklet.end_timestep) for tracklet in tracklets) == sorted(
            [(_frame_id("r1", 0), 6), (_frame_id("r1", 0, BACK), 4)]
        )

    def test_with_none_named_each_video_an_object_is_annotated_in(self, scene: _Scene) -> None:
        _annotate(scene, "car", "r1", 3, view=BACK)

        [chunk] = scene.plan(_params())

        assert chunk.payload == {"record_id": "r1", "view": BACK, "objects": [{"entity_id": "car", "frame_index": 3}]}


class TestTrackAgain:
    def test_a_track_from_a_later_frame_keeps_what_an_earlier_one_proposed_before_it(self, scene: _Scene) -> None:
        _annotate(scene, frame_index=0)
        scene.run(_params(objects=[_target(frame_index=0)]))
        before = {mask.frame_index: mask.id for mask in scene.masks()}
        # The model's mask drifted on frame 3: a person draws the box there, then tracks again from it.
        _annotate(scene, frame_index=3)

        scene.run(_params(objects=[_target(frame_index=3)]), job_id="job-2")

        # The person's box prompts, not the model's mask on that frame, which gives way to it.
        prompts = scene.inference.calls[-2].keyframes[0].prompts
        assert prompts.box is not None and prompts.mask is None
        masks = scene.masks()
        assert [mask.frame_index for mask in masks] == [1, 2, 4, 5, 6]
        kept = {mask.frame_index: mask.id for mask in masks if mask.frame_index < 3}
        assert kept == {index: before[index] for index in (1, 2)}
        [tracklet] = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        assert (tracklet.start_timestep, tracklet.end_timestep) == (1, 6)
        assert {mask.tracklet_id for mask in masks} == {tracklet.id}

    def test_a_track_from_a_models_mask_keeps_it(self, scene: _Scene) -> None:
        # Pointed at a frame where only the model's mask is: it prompts, and stays.
        _annotate(scene, frame_index=0)
        scene.run(_params(objects=[_target(frame_index=0)]))
        on_frame_3 = next(mask.id for mask in scene.masks() if mask.frame_index == 3)

        scene.run(_params(objects=[_target(frame_index=3)]), job_id="job-2")

        prompts = scene.inference.calls[-2].keyframes[0].prompts
        assert prompts.mask is not None and prompts.box is None
        assert [mask.frame_index for mask in scene.masks()] == [1, 2, 3, 4, 5, 6]
        assert next(mask.id for mask in scene.masks() if mask.frame_index == 3) == on_frame_3

    def test_a_persons_box_prompts_before_a_models_mask_from_the_jobs_panel(self, scene: _Scene) -> None:
        _annotate(scene, frame_index=1)
        _annotate(scene, frame_index=1, as_mask=True, source_type="model", review_status="pending")

        scene.run(_params())

        prompts = scene.inference.calls[0].keyframes[0].prompts
        assert prompts.box is not None and prompts.mask is None

    def test_the_tracklet_spans_the_masks_a_person_accepted(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.run(_params(objects=[_target()]))
        accepted = [mask for mask in scene.masks() if mask.frame_index >= 5]
        for mask in accepted:
            mask.review_status = "accepted"
        scene.dataset().update_data("masks", accepted)
        # The model now loses the car after frame 2.
        scene.inference.lost_after = 2

        scene.run(_params(objects=[_target()]), job_id="job-2")

        assert [mask.frame_index for mask in scene.masks()] == [1, 2, 5, 6]
        [tracklet] = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        assert (tracklet.start_timestep, tracklet.end_timestep) == (0, 6)
        assert {mask.tracklet_id for mask in scene.masks()} == {tracklet.id}

    def test_a_tracklet_is_kept_while_masks_a_person_accepted_name_it(self, scene: _Scene) -> None:
        _annotate(scene)
        scene.run(_params(objects=[_target()]))
        accepted = scene.masks()
        for mask in accepted:
            mask.review_status = "accepted"
        scene.dataset().update_data("masks", accepted)
        scene.inference.lost_after = 0

        scene.run(_params(objects=[_target()]), job_id="job-2")

        [tracklet] = scene.dataset().get_data("tracklets", where="entity_id = 'car'")
        assert (tracklet.start_timestep, tracklet.end_timestep) == (0, 6)
        assert {mask.tracklet_id for mask in scene.masks()} == {tracklet.id}
