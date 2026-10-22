/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ResourceMutation } from "$lib/api/resourcePayloads";
import { createSaveQueue } from "$lib/stores/saveQueue";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Tracklet,
  WorkspaceType,
  type View,
} from "$lib/types/dataset";
import { ShapeType, type EditShape } from "$lib/types/shapeTypes";
import { boxLinearInterpolation } from "$lib/utils/interpolation";

const NOW = "2026-03-31T00:00:00+00:00";

const mockEntitiesStore = {
  value: [] as Entity[],
  update(updater: (entities: Entity[]) => Entity[]) {
    this.value = updater(this.value);
  },
};

const mockAnnotationsStore = {
  value: [] as Annotation[],
  update(updater: (annotations: Annotation[]) => Annotation[]) {
    this.value = updater(this.value);
  },
};

const mockViewsStore = {
  value: {
    camera: [0, 1, 2, 3].map((frameIndex) => ({
      id: `camera-frame-${frameIndex}`,
      data: { frame_index: frameIndex, width: 100, height: 100 },
    })),
  } as Record<string, unknown>,
};

const mockSaveDataStore = {
  value: [] as ResourceMutation[],
  update(updater: (mutations: ResourceMutation[]) => ResourceMutation[]) {
    this.value = updater(this.value);
  },
};
const mockSaveQueue = createSaveQueue((mutations) => {
  mockSaveDataStore.value = mutations;
});

const mockEditedTrackletId = { value: null as string | null };

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  annotations: mockAnnotationsStore,
  editedTrackletId: mockEditedTrackletId,
  entities: mockEntitiesStore,
  itemMetas: { value: { type: WorkspaceType.VIDEO } },
  views: mockViewsStore,
  saveData: mockSaveDataStore,
  workspaceSaveQueue: mockSaveQueue,
}));

vi.mock("$lib/stores/workspaceBaseStores.svelte", () => ({
  saveData: mockSaveDataStore,
}));

vi.mock("$lib/stores/appStores.svelte", () => ({
  currentDatasetStore: { value: "" },
}));

vi.mock("$lib/stores/videoStores.svelte", () => ({
  currentFrameIndex: { value: 0 },
  currentItemId: { value: "" },
  imagesPerView: { value: {} },
  lastFrameIndex: { value: 0 },
  videoViewNames: { value: [] },
}));

function makeEntity(id = "entity-1"): Entity {
  const entity = new Entity({
    id,
    table_info: {
      name: "entities",
      group: "entities",
      base_schema: BaseSchema.Entity,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      parent_id: "",
    },
  });
  entity.ui.childs = [];
  return entity;
}

function makeBBox(
  id: string,
  entity: Entity,
  frameIndex: number,
  trackletId: string,
  coords: number[],
): BBox {
  const bbox = new BBox({
    id,
    table_info: {
      name: "bboxes",
      group: "annotations",
      base_schema: BaseSchema.BBox,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: entity.id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      tracklet_id: trackletId,
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      confidence: 1,
      coords,
      format: "xywh",
      is_normalized: true,
    },
  });
  bbox.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "self" },
    frame_index: frameIndex,
    top_entities: [entity],
  };
  return bbox;
}

function makeTracklet(id: string, entity: Entity, childs: BBox[]): Tracklet {
  const tracklet = new Tracklet({
    id,
    table_info: {
      name: "tracklets",
      group: "annotations",
      base_schema: BaseSchema.Tracklet,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: entity.id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      inference_metadata: {},
      start_frame: childs[0]?.ui.frame_index ?? 0,
      end_frame: childs[childs.length - 1]?.ui.frame_index ?? 0,
      start_timestamp: childs[0]?.ui.frame_index ?? 0,
      end_timestamp: childs[childs.length - 1]?.ui.frame_index ?? 0,
    },
  });
  tracklet.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    childs,
    top_entities: [entity],
  };
  return tracklet;
}

describe("videoTrackMutations", () => {
  beforeEach(async () => {
    const { currentFrameIndex } = await import("$lib/stores/videoStores.svelte");
    currentFrameIndex.value = 0;
    mockAnnotationsStore.value = [];
    mockEditedTrackletId.value = null;
    mockEntitiesStore.value = [];
    mockSaveDataStore.value = [];
    mockSaveQueue.reset();
  });

  it("keeps tracklet ownership when materializing an interpolated bbox into a keyframe", async () => {
    const { editKeyItemInTracklet } = await import("$lib/utils/videoShapeEditing");

    const entity = makeEntity();
    const startBBox = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-2", entity, 2, "track-1", [0.5, 0.2, 0.2, 0.2]);
    const interpolatedBBox = boxLinearInterpolation([startBBox, endBBox], 1, "camera-frame-1");
    if (!interpolatedBBox) {
      throw new Error("Expected interpolated bbox");
    }

    const shape: EditShape = {
      status: "editing",
      type: ShapeType.bbox,
      shapeId: interpolatedBBox.id,
      viewRef: { id: "camera-frame-1", name: "camera" },
      coords: [0.3, 0.2, 0.2, 0.2],
      highlighted: "self",
    };

    const result = editKeyItemInTracklet([startBBox, endBBox], shape, 1, [interpolatedBBox], []);

    expect(result.save_data.change_type).toBe("add");
    const createdBBox = result.save_data.data as BBox;
    // The ghost id (`start::frame`) stays ghost-only: the keyframe gets a fresh id.
    expect(createdBBox.id).not.toBe(interpolatedBBox.id);
    expect(createdBBox.id).not.toContain("::");
    expect(result.objects).toContain(createdBBox);
    expect(createdBBox.data.tracklet_id).toBe("track-1");
    expect(createdBBox.data.frame_id).toBe("camera-frame-1");
    expect(createdBBox.ui.frame_index).toBe(1);
  });

  it("copies the edited coords instead of adopting the shape's array", async () => {
    const { editKeyItemInTracklet } = await import("$lib/utils/videoShapeEditing");

    const entity = makeEntity();
    const startBBox = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-2", entity, 2, "track-1", [0.5, 0.2, 0.2, 0.2]);
    // The workspace hands over shapes read from a $state store, i.e. reactive proxies,
    // which structuredClone (used by the ghost derivation) refuses to clone.
    const coords = new Proxy([0.15, 0.2, 0.2, 0.2], {});
    const shape: EditShape = {
      status: "editing",
      type: ShapeType.bbox,
      shapeId: "bbox-0",
      viewRef: { id: "camera-frame-0", name: "camera" },
      coords,
      highlighted: "self",
    };

    const result = editKeyItemInTracklet([startBBox, endBBox], shape, 0, [], []);

    expect(result.save_data.change_type).toBe("update");
    expect(startBBox.data.coords).toEqual([0.15, 0.2, 0.2, 0.2]);
    expect(startBBox.data.coords).not.toBe(coords);
    expect(() => structuredClone(startBBox)).not.toThrow();
    expect(
      boxLinearInterpolation([startBBox, endBBox], 1, "camera-frame-1")?.data.coords[0],
    ).toBeCloseTo(0.325);
  });

  it("never matches a regenerated ghost against a materialised keyframe", async () => {
    const { editKeyItemInTracklet } = await import("$lib/utils/videoShapeEditing");

    const entity = makeEntity();
    const startBBox = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-2", entity, 2, "track-1", [0.5, 0.2, 0.2, 0.2]);
    const ghost = boxLinearInterpolation([startBBox, endBBox], 1, "camera-frame-1");
    if (!ghost) {
      throw new Error("Expected interpolated bbox");
    }
    const shape: EditShape = {
      status: "editing",
      type: ShapeType.bbox,
      shapeId: ghost.id,
      viewRef: { id: "camera-frame-1", name: "camera" },
      coords: [0.3, 0.2, 0.2, 0.2],
      highlighted: "self",
    };

    const first = editKeyItemInTracklet([startBBox, endBBox], shape, 1, [ghost], []);
    const keyframe = first.save_data.data as BBox;

    // The keyframe later moves to frame 3 (a keyframe-dot drag keeps its id), so the
    // ghost at frame 1 is derived again from the same start box, with the same id.
    keyframe.ui.frame_index = 3;
    const regenerated = boxLinearInterpolation([startBBox, endBBox], 1, "camera-frame-1");
    if (!regenerated) {
      throw new Error("Expected interpolated bbox");
    }
    expect(regenerated.id).toBe(ghost.id);

    const second = editKeyItemInTracklet(
      first.objects,
      { ...shape, coords: [0.35, 0.2, 0.2, 0.2] },
      1,
      [regenerated],
      [],
    );

    expect(second.save_data.change_type).toBe("add");
    expect(keyframe.data.coords).toEqual([0.3, 0.2, 0.2, 0.2]);
  });

  it("reassigns child ownership on both sides of a split tracklet", async () => {
    const { splitTrackInTwo } = await import("$lib/utils/videoOperations");

    const entity = makeEntity();
    const bbox0 = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const bbox1 = makeBBox("bbox-1", entity, 1, "track-1", [0.2, 0.2, 0.2, 0.2]);
    const bbox2 = makeBBox("bbox-2", entity, 2, "track-1", [0.3, 0.2, 0.2, 0.2]);
    const bbox3 = makeBBox("bbox-3", entity, 3, "track-1", [0.4, 0.2, 0.2, 0.2]);
    const tracklet = makeTracklet("track-1", entity, [bbox0, bbox1, bbox2, bbox3]);

    const rightTracklet = splitTrackInTwo(tracklet, 1, 2) as Tracklet;

    expect(tracklet.data.end_frame).toBe(1);
    expect(tracklet.ui.childs.map((annotation) => annotation.id)).toEqual(["bbox-0", "bbox-1"]);
    expect(
      tracklet.ui.childs.every((annotation) => annotation.data.tracklet_id === "track-1"),
    ).toBe(true);

    expect(rightTracklet.data.start_frame).toBe(2);
    expect(rightTracklet.ui.childs.map((annotation) => annotation.id)).toEqual([
      "bbox-2",
      "bbox-3",
    ]);
    expect(
      rightTracklet.ui.childs.every(
        (annotation) => annotation.data.tracklet_id === rightTracklet.id,
      ),
    ).toBe(true);
    // The moved keyframes are saved with their new track; the others are left alone.
    const childUpdates = mockSaveDataStore.value.filter(
      (mutation) => mutation.op === "update" && mutation.target.resource !== "tracklets",
    );
    expect(childUpdates.map((mutation) => mutation.target.id).sort()).toEqual(["bbox-2", "bbox-3"]);
  });

  it("splits right after an interpolated frame and keeps every box", async () => {
    const { splitTrackletAfter } = await import("$lib/utils/trackletOperations");

    const entity = makeEntity();
    const startBBox = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-3", entity, 3, "track-1", [0.4, 0.2, 0.2, 0.2]);
    const tracklet = makeTracklet("track-1", entity, [startBBox, endBBox]);
    entity.ui.childs = [tracklet, startBBox, endBBox];
    mockEntitiesStore.value = [entity];
    mockAnnotationsStore.value = [tracklet, startBBox, endBBox];

    const split = splitTrackletAfter(
      tracklet,
      entity,
      1,
      mockViewsStore.value as Record<string, View | View[]>,
    );

    expect(split).toBe(true);
    const tracklets = mockAnnotationsStore.value.filter((annotation) =>
      annotation.is_type(BaseSchema.Tracklet),
    ) as Tracklet[];
    const right = tracklets.find((candidate) => candidate.id !== "track-1");
    if (!right) throw new Error("Expected a right tracklet");
    expect([tracklet.data.start_frame, tracklet.data.end_frame]).toEqual([0, 1]);
    expect([right.data.start_frame, right.data.end_frame]).toEqual([2, 3]);
    // Frames 1 and 2 were interpolated: they became the parts' boundary keyframes.
    expect(tracklet.ui.childs.map((child) => child.ui.frame_index)).toEqual([0, 1]);
    expect(right.ui.childs.map((child) => child.ui.frame_index)).toEqual([2, 3]);
    const atFrame2 = right.ui.childs[0] as BBox;
    expect(atFrame2.data.coords[0]).toBeCloseTo(0.3);
    expect(atFrame2.data.frame_index).toBe(2);

    // Everything that changed is staged, with the moved keyframes on the right track.
    const staged = new Map(
      mockSaveDataStore.value.map((mutation) => [mutation.target.id, mutation] as const),
    );
    expect(staged.get(right.id)?.op).toBe("create");
    expect(staged.get("track-1")?.op).toBe("update");
    expect(staged.get(tracklet.ui.childs[1].id)?.op).toBe("create");
    expect(staged.get(atFrame2.id)?.op).toBe("create");
    expect(staged.get("bbox-3")?.op).toBe("update");
    expect(staged.has("bbox-0")).toBe(false);
    for (const id of [atFrame2.id, "bbox-3"]) {
      expect(JSON.stringify(staged.get(id))).toContain(right.id);
    }
  });

  it("adds a keyframe at the current frame with a fresh id (Add a point)", async () => {
    const { addKeyItemToTracklet } = await import("$lib/utils/trackletOperations");
    const { currentFrameIndex } = await import("$lib/stores/videoStores.svelte");

    const entity = makeEntity();
    const startBBox = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-2", entity, 2, "track-1", [0.5, 0.2, 0.2, 0.2]);
    const tracklet = makeTracklet("track-1", entity, [startBBox, endBBox]);
    entity.ui.childs = [tracklet, startBBox, endBBox];
    mockEntitiesStore.value = [entity];
    mockAnnotationsStore.value = [tracklet, startBBox, endBBox];
    currentFrameIndex.value = 1;

    // As displayed on the canvas: pixel coords, anchored for editing.
    const ghost = boxLinearInterpolation([startBBox, endBBox], 1, "camera-frame-1");
    if (!ghost) {
      throw new Error("Expected interpolated bbox");
    }
    ghost.data.coords = ghost.data.coords.map((value) => value * 100);
    ghost.ui.displayControl = { ...ghost.ui.displayControl, editing: true };

    const added = addKeyItemToTracklet(
      tracklet,
      entity,
      mockViewsStore.value as Record<string, View | View[]>,
      [ghost],
      [],
    );

    expect(added).toBe(true);
    const keyframe = mockAnnotationsStore.value.find(
      (annotation) =>
        annotation.is_type(BaseSchema.BBox) && ![startBBox.id, endBBox.id].includes(annotation.id),
    ) as BBox;
    expect(keyframe.id).not.toBe(ghost.id);
    expect(keyframe.id).not.toContain("::");
    // Committing re-derives ui.frame_index from data.frame_index: both must be frame 1.
    expect(keyframe.data.frame_index).toBe(1);
    expect(keyframe.ui.frame_index).toBe(1);
    expect(keyframe.data.frame_id).toBe("camera-frame-1");
    expect(keyframe.data.tracklet_id).toBe("track-1");
    [0.3, 0.2, 0.2, 0.2].forEach((value, index) =>
      expect(keyframe.data.coords[index]).toBeCloseTo(value),
    );
    expect(keyframe.ui.displayControl.editing).toBe(false);
    expect(tracklet.ui.childs.map((annotation) => annotation.id)).toEqual([
      startBBox.id,
      keyframe.id,
      endBBox.id,
    ]);
    expect(mockSaveDataStore.value.map((mutation) => [mutation.op, mutation.target.id])).toEqual([
      ["create", keyframe.id],
    ]);
  });

  it("glues a neighbour track on, saving the range and the keyframes it moves", async () => {
    const { glueTracklets } = await import("$lib/utils/trackletOperations");

    const entity = makeEntity();
    const left = [
      makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]),
      makeBBox("bbox-1", entity, 1, "track-1", [0.2, 0.2, 0.2, 0.2]),
    ];
    const right = [
      makeBBox("bbox-2", entity, 2, "track-2", [0.3, 0.2, 0.2, 0.2]),
      makeBBox("bbox-3", entity, 3, "track-2", [0.4, 0.2, 0.2, 0.2]),
    ];
    const track1 = makeTracklet("track-1", entity, left);
    const track2 = makeTracklet("track-2", entity, right);
    entity.ui.childs = [track1, track2, ...left, ...right];
    mockEntitiesStore.value = [entity];
    mockAnnotationsStore.value = [track1, track2, ...left, ...right];
    mockEditedTrackletId.value = "track-2";

    glueTracklets(track1, track2, entity.id);

    expect([track1.data.start_frame, track1.data.end_frame]).toEqual([0, 3]);
    expect(track1.ui.childs.map((child) => child.id)).toEqual([
      "bbox-0",
      "bbox-1",
      "bbox-2",
      "bbox-3",
    ]);
    expect(mockAnnotationsStore.value.some((annotation) => annotation.id === "track-2")).toBe(
      false,
    );
    expect(mockEditedTrackletId.value).toBe("track-1");
    const staged = new Map(
      mockSaveDataStore.value.map((mutation) => [mutation.target.id, mutation] as const),
    );
    expect(staged.get("track-1")?.op).toBe("update");
    expect(staged.get("track-2")?.op).toBe("delete");
    expect(staged.get("bbox-2")?.op).toBe("update");
    expect(staged.get("bbox-3")?.op).toBe("update");
    expect(JSON.stringify(staged.get("bbox-3"))).toContain("track-1");
    expect(staged.has("bbox-0")).toBe(false);
  });
});

function frames(viewName: string, indexes: number[]) {
  return indexes.map((frameIndex) => ({
    id: `${viewName}-frame-${frameIndex}`,
    data: { frame_index: frameIndex, width: 100, height: 100, timestamp: frameIndex / 25 },
  }));
}

function makeKeypoints(id: string, entity: Entity, frameIndex: number, trackletId: string) {
  const keypoints = new Keypoints({
    id,
    table_info: { name: "keypoints", group: "annotations", base_schema: BaseSchema.Keypoints },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      entity_id: entity.id,
      source_type: "ground_truth",
      source_name: "Pixano",
      source_metadata: "{}",
      view_name: "camera",
      view_id: `camera-frame-${frameIndex}`,
      inference_metadata: {},
      tracklet_id: trackletId,
      entity_dynamic_state_id: "state-of-frame",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      template_id: "face",
      coords: [0.2, 0.2, 0.4, 0.2],
      states: ["visible", "visible"],
    },
  });
  keypoints.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    frame_index: frameIndex,
    top_entities: [entity],
  };
  return keypoints;
}

function trackOf(id: string, entity: Entity, childs: Annotation[], view = "camera"): Tracklet {
  const tracklet = makeTracklet(id, entity, childs as BBox[]);
  tracklet.data.view_name = view;
  return tracklet;
}

function boxIn(view: string, id: string, entity: Entity, frameIndex: number, trackletId: string) {
  const bbox = makeBBox(id, entity, frameIndex, trackletId, [0.1, 0.2, 0.2, 0.2]);
  bbox.data.view_name = view;
  bbox.data.frame_id = `${view}-frame-${frameIndex}`;
  return bbox;
}

function load(entity: Entity, annotations: Annotation[]) {
  entity.ui.childs = annotations.filter((annotation) => annotation.data.entity_id === entity.id);
  mockEntitiesStore.value = [entity];
  mockAnnotationsStore.value = annotations;
}

function staged() {
  return new Map(
    mockSaveDataStore.value.map((mutation) => [mutation.target.id, mutation] as const),
  );
}

describe("retimeKeyframe", () => {
  const defaultViews = mockViewsStore.value;
  let seek: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    const { lastFrameIndex } = await import("$lib/stores/videoStores.svelte");
    lastFrameIndex.value = 9;
    mockViewsStore.value = {
      camera: frames("camera", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
      left: frames("left", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
    };
    mockAnnotationsStore.value = [];
    mockEntitiesStore.value = [];
    mockSaveDataStore.value = [];
    mockSaveQueue.reset();
    seek = vi.fn();
  });

  afterEach(async () => {
    const { lastFrameIndex } = await import("$lib/stores/videoStores.svelte");
    lastFrameIndex.value = 0;
    mockViewsStore.value = defaultViews;
  });

  it("moves every annotation of a middle keyframe and keeps the new frame (PIX-118)", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const bbox0 = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const bbox2 = makeBBox("bbox-2", entity, 2, "track-1", [0.2, 0.2, 0.2, 0.2]);
    bbox2.data.view_id = "camera-frame-2";
    const kp2 = makeKeypoints("kp-2", entity, 2, "track-1");
    const bbox4 = makeBBox("bbox-4", entity, 4, "track-1", [0.3, 0.2, 0.2, 0.2]);
    const track = trackOf("track-1", entity, [bbox0, bbox2, kp2, bbox4]);
    load(entity, [track, bbox0, bbox2, kp2, bbox4]);

    const outcome = retimeKeyframe(
      { entityId: entity.id, frame: 2, trackletIds: ["track-1"], target: 3 },
      { seek },
    );

    expect(outcome).toEqual({ ok: true, frame: 3, movedIds: ["bbox-2", "kp-2"] });
    for (const moved of [bbox2, kp2]) {
      // Normalization re-derives ui.frame_index from data.frame_index: both must agree.
      expect(moved.ui.frame_index).toBe(3);
      expect(moved.data.frame_index).toBe(3);
      expect(moved.data.frame_id).toBe("camera-frame-3");
      expect(moved.data.view_id).toBe("camera-frame-3");
      expect(moved.data.entity_dynamic_state_id).toBe("");
    }
    expect(track.ui.childs.map((child) => child.ui.frame_index)).toEqual([0, 3, 3, 4]);
    expect([track.data.start_frame, track.data.end_frame]).toEqual([0, 4]);
    const mutations = staged();
    expect(mutations.get("bbox-2")?.op).toBe("update");
    expect(mutations.get("kp-2")?.op).toBe("update");
    expect(JSON.stringify(mutations.get("bbox-2"))).toContain("camera-frame-3");
    expect(mutations.has("track-1")).toBe(false);
    expect(mutations.has("bbox-0")).toBe(false);
    expect(seek).toHaveBeenCalledWith(3);
  });

  it("drags the track's end with its last keyframe, and its start with its first", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const bbox0 = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const bbox4 = makeBBox("bbox-4", entity, 4, "track-1", [0.3, 0.2, 0.2, 0.2]);
    const track = trackOf("track-1", entity, [bbox0, bbox4]);
    load(entity, [track, bbox0, bbox4]);

    expect(
      retimeKeyframe(
        { entityId: entity.id, frame: 4, trackletIds: ["track-1"], target: 6 },
        { seek },
      ).ok,
    ).toBe(true);
    expect([track.data.start_frame, track.data.end_frame]).toEqual([0, 6]);
    // The app stores frame numbers as tracklet timestamps: they follow the range.
    expect([track.data.start_timestamp, track.data.end_timestamp]).toEqual([0, 6]);
    const update = JSON.stringify(staged().get("track-1"));
    expect(update).toContain('"end_timestep":6');

    expect(
      retimeKeyframe(
        { entityId: entity.id, frame: 0, trackletIds: ["track-1"], target: 1 },
        { seek },
      ).ok,
    ).toBe(true);
    expect([track.data.start_frame, track.data.end_frame]).toEqual([1, 6]);
  });

  it("moves a single-keyframe track whole", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const bbox7 = makeBBox("bbox-7", entity, 7, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const track = trackOf("track-1", entity, [bbox7]);
    load(entity, [track, bbox7]);

    retimeKeyframe(
      { entityId: entity.id, frame: 7, trackletIds: ["track-1"], target: 9 },
      { seek },
    );

    expect([track.data.start_frame, track.data.end_frame]).toEqual([9, 9]);
    expect(bbox7.data.frame_index).toBe(9);
  });

  it("refuses a move past a neighbour and changes nothing", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const bbox0 = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const bbox2 = makeBBox("bbox-2", entity, 2, "track-1", [0.2, 0.2, 0.2, 0.2]);
    const bbox4 = makeBBox("bbox-4", entity, 4, "track-1", [0.3, 0.2, 0.2, 0.2]);
    const track = trackOf("track-1", entity, [bbox0, bbox2, bbox4]);
    load(entity, [track, bbox0, bbox2, bbox4]);

    for (const target of [4, 0, 5]) {
      expect(
        retimeKeyframe(
          { entityId: entity.id, frame: 2, trackletIds: ["track-1"], target },
          { seek },
        ),
      ).toEqual({ ok: false, reason: "out-of-bounds" });
    }
    expect(
      retimeKeyframe(
        { entityId: entity.id, frame: 2, trackletIds: ["track-1"], target: 2 },
        { seek },
      ),
    ).toEqual({ ok: false, reason: "same-frame" });
    expect(
      retimeKeyframe(
        { entityId: entity.id, frame: 3, trackletIds: ["track-1"], target: 1 },
        { seek },
      ),
    ).toEqual({ ok: false, reason: "no-keyframe" });
    expect(bbox2.data.frame_index).toBe(2);
    expect(mockSaveDataStore.value).toEqual([]);
    expect(seek).not.toHaveBeenCalled();
  });

  it("refuses a target frame a camera does not have", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    mockViewsStore.value = { camera: frames("camera", [0, 1, 2, 4, 5, 6]) };
    const entity = makeEntity();
    const bbox0 = makeBBox("bbox-0", entity, 0, "track-1", [0.1, 0.2, 0.2, 0.2]);
    const bbox2 = makeBBox("bbox-2", entity, 2, "track-1", [0.2, 0.2, 0.2, 0.2]);
    const bbox6 = makeBBox("bbox-6", entity, 6, "track-1", [0.3, 0.2, 0.2, 0.2]);
    const track = trackOf("track-1", entity, [bbox0, bbox2, bbox6]);
    load(entity, [track, bbox0, bbox2, bbox6]);

    expect(
      retimeKeyframe(
        { entityId: entity.id, frame: 2, trackletIds: ["track-1"], target: 3 },
        { seek },
      ),
    ).toEqual({ ok: false, reason: "no-frame" });
    expect(bbox2.data.frame_index).toBe(2);
    expect(mockSaveDataStore.value).toEqual([]);
  });

  it("is bounded by the entity's other tracks of the camera, not by other entities'", async () => {
    const { keyframeRetimeBoundsFor } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const other = makeEntity("entity-2");
    const a0 = makeBBox("a-0", entity, 0, "track-a", [0.1, 0.2, 0.2, 0.2]);
    const a3 = makeBBox("a-3", entity, 3, "track-a", [0.1, 0.2, 0.2, 0.2]);
    const b6 = makeBBox("b-6", entity, 6, "track-b", [0.1, 0.2, 0.2, 0.2]);
    const b8 = makeBBox("b-8", entity, 8, "track-b", [0.1, 0.2, 0.2, 0.2]);
    const o5 = makeBBox("o-5", other, 5, "track-o", [0.1, 0.2, 0.2, 0.2]);
    const trackA = trackOf("track-a", entity, [a0, a3]);
    const trackB = trackOf("track-b", entity, [b6, b8]);
    const trackO = trackOf("track-o", other, [o5]);
    load(entity, [trackA, trackB, trackO, a0, a3, b6, b8, o5]);

    expect(
      keyframeRetimeBoundsFor({ entityId: entity.id, frame: 3, trackletIds: ["track-a"] }),
    ).toEqual({ min: 1, max: 5 });
  });

  it("moves the keyframe of every camera of a merged row, each to its own frame", async () => {
    const { retimeKeyframe } = await import("$lib/utils/trackletOperations");
    const entity = makeEntity();
    const c0 = boxIn("camera", "c-0", entity, 0, "track-c");
    const c5 = boxIn("camera", "c-5", entity, 5, "track-c");
    const l5 = boxIn("left", "l-5", entity, 5, "track-l");
    const l9 = boxIn("left", "l-9", entity, 9, "track-l");
    const trackC = trackOf("track-c", entity, [c0, c5], "camera");
    const trackL = trackOf("track-l", entity, [l5, l9], "left");
    load(entity, [trackC, trackL, c0, c5, l5, l9]);

    const outcome = retimeKeyframe(
      { entityId: entity.id, frame: 5, trackletIds: ["track-c", "track-l"], target: 6 },
      { seek },
    );

    expect(outcome.ok).toBe(true);
    expect(c5.data.frame_id).toBe("camera-frame-6");
    expect(l5.data.frame_id).toBe("left-frame-6");
    expect([trackC.data.start_frame, trackC.data.end_frame]).toEqual([0, 6]);
    expect([trackL.data.start_frame, trackL.data.end_frame]).toEqual([6, 9]);
  });
});
