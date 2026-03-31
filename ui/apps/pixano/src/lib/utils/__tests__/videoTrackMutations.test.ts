/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import { BaseSchema, BBox, Entity, Tracklet, WorkspaceType } from "$lib/types/dataset";
import { ShapeType, type EditShape } from "$lib/types/shapeTypes";
import { boxLinearInterpolation } from "$lib/utils/interpolation";

const NOW = "2026-03-31T00:00:00+00:00";

const mockEntitiesStore = {
  value: [] as Entity[],
  update(updater: (entities: Entity[]) => Entity[]) {
    this.value = updater(this.value);
  },
};

const mockViewsStore = {
  value: {
    camera: [
      { id: "camera-frame-0", data: { frame_index: 0 } },
      { id: "camera-frame-1", data: { frame_index: 1 } },
      { id: "camera-frame-2", data: { frame_index: 2 } },
      { id: "camera-frame-3", data: { frame_index: 3 } },
    ],
  } as Record<string, unknown>,
};

const mockSaveDataStore = {
  value: [] as unknown[],
  update(updater: (mutations: unknown[]) => unknown[]) {
    this.value = updater(this.value);
  },
};

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  entities: mockEntitiesStore,
  views: mockViewsStore,
  saveData: mockSaveDataStore,
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
  beforeEach(() => {
    mockEntitiesStore.value = [];
    mockSaveDataStore.value = [];
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

    const createdBBox = result.objects.find(
      (annotation) => annotation.id === interpolatedBBox.id,
    ) as BBox | undefined;
    expect(result.save_data.change_type).toBe("add");
    expect(createdBBox?.data.tracklet_id).toBe("track-1");
    expect(createdBBox?.data.frame_id).toBe("camera-frame-1");
    expect(createdBBox?.ui.frame_index).toBe(1);
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
  });
});
