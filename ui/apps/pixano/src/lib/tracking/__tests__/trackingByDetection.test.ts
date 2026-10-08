/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  applyKeyframeStride,
  applyScoreThreshold,
  buildTrackingByDetectionRequest,
  collectDetectionTracks,
  DEFAULT_TRACKING_BY_DETECTION_PARAMS,
  estimateTrackingByDetectionRows,
  interpolateSegmentAt,
  parseClassList,
  resolveTrackingWindow,
  splitTrackIntoSegments,
  type DetectionTrack,
  type DetectionTrackFrame,
  type TrackingFrameSource,
} from "../trackingByDetection";
import { buildTrackingByDetectionRows } from "../trackingByDetectionRows";
import { BaseSchema, WorkspaceType } from "$lib/types/dataset";
import type { VideoTrackedFrame } from "$lib/types/inference";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  entities: { value: [] },
  views: { value: {} },
}));

const sources: TrackingFrameSource[] = [0, 1, 2, 3, 4, 5].map((frameIndex) => ({
  frameIndex,
  frameId: `frame-${frameIndex}`,
  width: 200,
  height: 100,
}));

function frame(
  frameIndex: number,
  coords: [number, number, number, number],
  extra = {},
): DetectionTrackFrame {
  return {
    frameIndex,
    frameId: `frame-${frameIndex}`,
    coords,
    score: 0.9,
    className: "person",
    ...extra,
  };
}

function track(
  trackId: number,
  frames: DetectionTrackFrame[],
  className: string | null = "person",
): DetectionTrack {
  const scores = frames.map((f) => f.score);
  return {
    trackId,
    className,
    frames,
    startFrame: frames[0].frameIndex,
    endFrame: frames[frames.length - 1].frameIndex,
    meanScore: scores.reduce((a, b) => a + b, 0) / scores.length,
    detectionCount: frames.length,
  };
}

const manifest = {
  workspaceType: WorkspaceType.VIDEO,
  tablesByName: {
    objects: {
      name: "objects",
      group: "entities",
      baseSchema: BaseSchema.Entity,
      fields: { category: { type: "str" } },
    },
    bboxes: { name: "bboxes", group: "annotations", baseSchema: BaseSchema.BBox, fields: {} },
    tracklets: {
      name: "tracklets",
      group: "annotations",
      baseSchema: BaseSchema.Tracklet,
      fields: {},
    },
  },
  tablesByGroup: {
    entities: ["objects"],
    annotations: ["bboxes", "tracklets"],
    views: ["image"],
    embeddings: [],
    item: [],
  },
  relations: {},
  baseSchemaToTable: {
    entities: { [BaseSchema.Entity]: "objects" },
    annotations: { [BaseSchema.BBox]: "bboxes", [BaseSchema.Tracklet]: "tracklets" },
  },
} as unknown as WorkspaceManifest;

describe("resolveTrackingWindow / buildTrackingByDetectionRequest", () => {
  it("covers the whole view or from the current frame", () => {
    expect(resolveTrackingWindow(sources, null)).toEqual({
      startFrameIndex: 0,
      endFrameIndex: 5,
      frameCount: 6,
    });
    expect(resolveTrackingWindow(sources, 4)).toEqual({
      startFrameIndex: 4,
      endFrameIndex: 5,
      frameCount: 2,
    });
    expect(resolveTrackingWindow(sources, 9)).toBeNull();
  });

  it("builds a prompt-free request", () => {
    const request = buildTrackingByDetectionRequest({
      model: "yolo-bytetrack",
      providerName: "pixano-inference",
      datasetId: "d",
      recordId: "r",
      viewName: "image",
      window: { startFrameIndex: 2, endFrameIndex: 5, frameCount: 4 },
      classes: ["person"],
      boxThreshold: 0.4,
    });
    expect(request).toEqual({
      model: "yolo-bytetrack",
      provider_name: "pixano-inference",
      dataset_id: "d",
      record_id: "r",
      view_name: "image",
      start_frame_index: 2,
      frame_count: 4,
      objects_ids: [],
      prompt_frame_indexes: [],
      propagate: true,
      classes: ["person"],
      box_threshold: 0.4,
    });
    expect(request).not.toHaveProperty("keyframes");
    expect(buildTrackingByDetectionRequest({ ...requestInput(), classes: [] }).classes).toBeNull();
  });

  it("parses typed class lists", () => {
    expect(parseClassList(" person, car\ncar,,bike ")).toEqual(["person", "car", "bike"]);
    expect(parseClassList("")).toEqual([]);
  });
});

function requestInput() {
  return {
    model: "m",
    providerName: "p",
    datasetId: "d",
    recordId: "r",
    viewName: "image",
    window: { startFrameIndex: 0, endFrameIndex: 1, frameCount: 2 },
    classes: ["x"],
    boxThreshold: 0.5,
  };
}

describe("collectDetectionTracks", () => {
  const result: VideoTrackedFrame[] = [
    {
      frame_index: 0,
      objects: [{ track_id: 1, box: [20, 10, 60, 60], score: 0.8, class_name: "person" }],
    },
    {
      frame_index: 1,
      objects: [
        { track_id: 1, box: [22, 10, 62, 60], score: 0.6, class_name: "person" },
        { track_id: 2, box: [100, 0, 200, 100], score: 0.95, class_name: "car" },
        { track_id: 3, mask: { size: [100, 200], counts: "abc" } },
      ],
    },
    {
      frame_index: 2,
      objects: [{ track_id: 1, box: [24, 10, 64, 60], score: 1.0, class_name: "dog" }],
    },
    { frame_index: 42, objects: [{ track_id: 2, box: [0, 0, 1, 1], score: 0.5 }] },
  ];

  it("groups boxes by track, normalized by the frame size, and skips what it cannot place", () => {
    const { tracks, skipped } = collectDetectionTracks(result, sources);
    expect(skipped).toEqual({ noBox: 1, unknownFrame: 1 });
    expect(tracks.map((t) => t.trackId)).toEqual([1, 2]);
    const person = tracks[0];
    expect(person.frames.map((f) => f.frameIndex)).toEqual([0, 1, 2]);
    expect(person.frames[0].coords).toEqual([0.1, 0.1, 0.2, 0.5]);
    expect(person.frames[0].frameId).toBe("frame-0");
    expect(person.className).toBe("person");
    expect(person.meanScore).toBeCloseTo(0.8);
    expect(person.detectionCount).toBe(3);
    expect(tracks[1]).toMatchObject({ trackId: 2, className: "car", startFrame: 1, endFrame: 1 });
  });

  it("keeps the higher-scoring box when a track appears twice in a frame and clamps to the frame", () => {
    const { tracks } = collectDetectionTracks(
      [
        {
          frame_index: 0,
          objects: [
            { track_id: 7, box: [0, 0, 10, 10], score: 0.2 },
            { track_id: 7, box: [-10, -10, 250, 150], score: 0.9 },
          ],
        },
      ],
      sources,
    );
    expect(tracks).toHaveLength(1);
    expect(tracks[0].frames[0].score).toBe(0.9);
    expect(tracks[0].frames[0].coords).toEqual([0, 0, 1, 1]);
    expect(tracks[0].className).toBeNull();
  });
});

describe("threshold, segments, stride, interpolation", () => {
  it("filters whole tracks on their mean score", () => {
    const low = track(1, [frame(0, [0, 0, 0.1, 0.1], { score: 0.2 })]);
    const high = track(2, [frame(0, [0, 0, 0.1, 0.1], { score: 0.7 })]);
    expect(applyScoreThreshold([low, high], 0.5).map((t) => t.trackId)).toEqual([2]);
  });

  it("splits a track into runs when it is missing for more than the gap", () => {
    const t = track(
      1,
      [0, 1, 2, 10, 11, 50].map((i) => frame(i, [0, 0, 0.1, 0.1])),
    );
    expect(splitTrackIntoSegments(t, 5).map((s) => [s.startFrame, s.endFrame])).toEqual([
      [0, 2],
      [10, 11],
      [50, 50],
    ]);
    expect(splitTrackIntoSegments(t, 100)).toHaveLength(1);
  });

  it("keeps the first, every Nth and the last frame of a run", () => {
    const segment = {
      startFrame: 3,
      endFrame: 11,
      frames: [3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => frame(i, [0, 0, 0.1, 0.1])),
    };
    expect(applyKeyframeStride(segment, 4).map((f) => f.frameIndex)).toEqual([3, 7, 11]);
    expect(applyKeyframeStride(segment, 1).map((f) => f.frameIndex)).toEqual([
      3, 4, 5, 6, 7, 8, 9, 10, 11,
    ]);
    const short = {
      startFrame: 0,
      endFrame: 1,
      frames: [frame(0, [0, 0, 0.1, 0.1]), frame(1, [0, 0, 0.1, 0.1])],
    };
    expect(applyKeyframeStride(short, 10).map((f) => f.frameIndex)).toEqual([0, 1]);
  });

  it("interpolates between kept boxes and stops outside the run", () => {
    const keyframes = [frame(0, [0, 0, 0.2, 0.2]), frame(4, [0.4, 0.4, 0.2, 0.2])];
    expect(interpolateSegmentAt(keyframes, 2)).toEqual({
      coords: [0.2, 0.2, 0.2, 0.2],
      isKeyframe: false,
    });
    expect(interpolateSegmentAt(keyframes, 4)).toEqual({
      coords: [0.4, 0.4, 0.2, 0.2],
      isKeyframe: true,
    });
    expect(interpolateSegmentAt(keyframes, 5)).toBeNull();
    expect(interpolateSegmentAt([], 0)).toBeNull();
  });
});

describe("buildTrackingByDetectionRows", () => {
  const params = { ...DEFAULT_TRACKING_BY_DETECTION_PARAMS, keyframeStride: 2, maxGapFrames: 3 };
  const tracks = [
    track(
      1,
      [0, 1, 2, 3, 4].map((i) => frame(i, [0.1, 0.1, 0.2, 0.5], { score: 0.5 + i / 10 })),
    ),
    track(
      2,
      [0, 5].map((i) => frame(i, [0.5, 0.5, 0.1, 0.1])),
      null,
    ),
  ];

  function build(labelField: string | null) {
    return buildTrackingByDetectionRows({
      tracks,
      params,
      itemId: "item-1",
      viewName: "image",
      manifest,
      labelField,
      source: { modelName: "yolo-bytetrack", providerName: "pixano-inference" },
      frameSize: { width: 200, height: 100 },
    });
  }

  it("creates one entity per track, one tracklet per run and one bbox per kept frame", () => {
    const rows = build("category");
    expect(rows.entities).toHaveLength(2);
    expect(rows.entities[0].data).toMatchObject({ item_id: "item-1", category: "person" });
    expect(rows.entities[1].data).not.toHaveProperty("category");
    expect(rows.classValues).toEqual(["person"]);

    expect(rows.tracklets).toHaveLength(3);
    const [run1, run2a, run2b] = rows.tracklets;
    expect(run1.data).toMatchObject({
      entity_id: rows.entities[0].id,
      start_frame: 0,
      end_frame: 4,
      source_type: "model",
      source_name: "yolo-bytetrack",
      view_name: "image",
    });
    expect(run2a.data).toMatchObject({
      entity_id: rows.entities[1].id,
      start_frame: 0,
      end_frame: 0,
    });
    expect(run2b.data).toMatchObject({
      entity_id: rows.entities[1].id,
      start_frame: 5,
      end_frame: 5,
    });

    expect(rows.bboxes.map((b) => b.data.frame_index)).toEqual([0, 2, 4, 0, 5]);
    const first = rows.bboxes[0];
    expect(first.data).toMatchObject({
      entity_id: rows.entities[0].id,
      tracklet_id: run1.id,
      frame_id: "frame-0",
      frame_index: 0,
      view_id: "frame-0",
      coords: [0.1, 0.1, 0.2, 0.5],
      format: "xywh",
      is_normalized: true,
      confidence: 0.5,
      source_type: "model",
      source_name: "yolo-bytetrack",
    });
    expect(JSON.parse(first.data.source_metadata)).toEqual({
      provider_name: "pixano-inference",
      track_id: 1,
      class: "person",
    });
    expect(first.ui.datasetItemType).toBe(WorkspaceType.VIDEO);
    expect(first.ui.frame_index).toBe(0);
    expect(run1.ui.childs).toHaveLength(3);
    expect(rows.entities[0].ui.childs).toHaveLength(4);
    expect(estimateTrackingByDetectionRows(tracks, params)).toEqual({
      entities: 2,
      tracklets: 3,
      bboxes: 5,
    });
  });

  it("keeps the class in the provenance only when the entity table has no label field", () => {
    const rows = build(null);
    expect(rows.entities[0].data).not.toHaveProperty("category");
    expect(rows.classValues).toEqual([]);
    expect(JSON.parse(rows.bboxes[0].data.source_metadata)).toMatchObject({
      class: "person",
    });
  });
});
