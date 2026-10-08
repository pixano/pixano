/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import { acceptTrackingByDetection } from "../trackingByDetectionAccept";
import {
  DEFAULT_TRACKING_BY_DETECTION_PARAMS,
  type DetectionTrack,
} from "$lib/tracking/trackingByDetection";
import { BaseSchema, WorkspaceType, type FeaturesValues } from "$lib/types/dataset";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

// Hoisted with the mocks: vi.mock factories run before the module's own top level.
const { session, kept, mocks } = vi.hoisted(() => ({
  session: { value: {} as Record<string, unknown> },
  kept: { value: [] as DetectionTrack[] },
  mocks: { saveTo: vi.fn(), commit: vi.fn(), reset: vi.fn() },
}));

vi.mock("$lib/stores/trackingByDetectionStore.svelte", () => ({
  trackingByDetectionSession: session,
  keptDetectionTracks: kept,
  resetTrackingByDetectionSession: mocks.reset,
  resolveTrackingFrameSources: () => [
    { frameIndex: 0, frameId: "frame-0", width: 200, height: 100 },
    { frameIndex: 1, frameId: "frame-1", width: 200, height: 100 },
  ],
}));
vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  annotations: { value: [] },
  entities: { value: [] },
  views: { value: {} },
}));
vi.mock("$lib/utils/saveItemUtils", () => ({ saveTo: mocks.saveTo }));
vi.mock("$lib/utils/workspaceRuntimeMutations", () => ({
  commitNormalizedWorkspaceRuntime: mocks.commit,
}));

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

function reviewState(): Record<string, unknown> {
  return {
    phase: "review",
    params: { ...DEFAULT_TRACKING_BY_DETECTION_PARAMS, keyframeStride: 1 },
    target: { datasetId: "dataset-1", recordId: "record-1" },
    viewName: "image",
    run: { model: "yolo-bytetrack", providerName: "pixano-inference" },
  };
}

const frames = [0, 1].map((frameIndex) => ({
  frameIndex,
  frameId: `frame-${frameIndex}`,
  coords: [0.1, 0.1, 0.2, 0.2] as [number, number, number, number],
  score: 0.8,
  className: "person",
}));

describe("acceptTrackingByDetection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    session.value = reviewState();
    kept.value = [
      {
        trackId: 1,
        className: "person",
        frames,
        startFrame: 0,
        endFrame: 1,
        meanScore: 0.8,
        detectionCount: 2,
      },
    ];
  });

  it("stages entities, tracklets and boxes, commits the runtime, records the class and closes", () => {
    const featureValues: FeaturesValues = { main: {}, objects: {} };

    const result = acceptTrackingByDetection({ manifest, featureValues });

    expect(result).toEqual({ entities: 1, tracklets: 1, bboxes: 2, labelField: "category" });
    const staged = mocks.saveTo.mock.calls.map(
      ([op, row]: [string, { table_info: { name: string } }]) => [op, row.table_info.name],
    );
    expect(staged).toEqual([
      ["add", "objects"],
      ["add", "tracklets"],
      ["add", "bboxes"],
      ["add", "bboxes"],
    ]);
    expect(mocks.commit).toHaveBeenCalledTimes(1);
    const [committedAnnotations, committedEntities] = mocks.commit.mock.calls[0] as [
      unknown[],
      unknown[],
    ];
    expect(committedAnnotations).toHaveLength(3);
    expect(committedEntities).toHaveLength(1);
    expect(featureValues.objects.category?.values).toEqual(["person"]);
    expect(mocks.reset).toHaveBeenCalledTimes(1);
  });

  it("does nothing outside a review", () => {
    session.value = { ...reviewState(), phase: "running" };
    expect(acceptTrackingByDetection({ manifest, featureValues: undefined })).toBeNull();
    expect(mocks.saveTo).not.toHaveBeenCalled();
    expect(mocks.reset).not.toHaveBeenCalled();
  });
});
