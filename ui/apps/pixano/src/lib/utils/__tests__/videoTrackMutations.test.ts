/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ResourceMutation } from "$lib/api/resourcePayloads";
import { createSaveQueue } from "$lib/stores/saveQueue";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
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

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  annotations: mockAnnotationsStore,
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
});
