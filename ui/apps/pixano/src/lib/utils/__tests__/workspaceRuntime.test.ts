/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { boxLinearInterpolation } from "$lib/utils/interpolation";
import {
  collectFrameAnnotations,
  getBBoxInterpolationIdentity,
} from "$lib/stores/frameAnnotationSelectors";
import {
  BaseSchema,
  BBox,
  Entity,
  Image,
  Item,
  SequenceFrame,
  Tracklet,
  WorkspaceType,
} from "$lib/types/dataset";
import { ToolType } from "$lib/types/tools";
import type { WorkspaceData } from "$lib/types/workspace";

const NOW = "2026-03-31T00:00:00+00:00";

const mockEntitiesStore = {
  value: [] as Entity[],
};

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  entities: mockEntitiesStore,
}));

function makeFrame(viewName: string, frameIndex: number): SequenceFrame {
  return new SequenceFrame({
    id: `${viewName}-frame-${frameIndex}`,
    table_info: {
      name: "frames",
      group: "views",
      base_schema: BaseSchema.SequenceFrame,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      parent_id: "",
      view_name: viewName,
      url: "",
      width: 100,
      height: 100,
      format: "png",
      timestamp: frameIndex,
      frame_index: frameIndex,
    },
  });
}

function makeItem(id = "item-1"): Item {
  return new Item({
    id,
    table_info: {
      name: "items",
      group: "item",
      base_schema: BaseSchema.Item,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {},
  });
}

function makeImage(viewName = "camera"): Image {
  return new Image({
    id: `${viewName}-image`,
    table_info: {
      name: "images",
      group: "views",
      base_schema: BaseSchema.Image,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      parent_id: "",
      view_name: viewName,
      url: "",
      width: 100,
      height: 100,
      format: "png",
    },
  });
}

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

function makeTracklet(
  id: string,
  entity: Entity,
  startFrame: number,
  endFrame: number,
  viewName = "camera",
): Tracklet {
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
      view_name: viewName,
      inference_metadata: {},
      start_frame: startFrame,
      end_frame: endFrame,
      start_timestamp: startFrame,
      end_timestamp: endFrame,
    },
  });
  tracklet.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "all" },
    childs: [],
    top_entities: [entity],
  };
  return tracklet;
}

function makeBBox(
  id: string,
  entity: Entity,
  frameIndex: number,
  trackletId = "",
  coords: number[] = [0.1, 0.2, 0.3, 0.4],
  viewName = "camera",
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
      view_name: viewName,
      inference_metadata: {},
      tracklet_id: trackletId,
      entity_dynamic_state_id: "",
      frame_id: `${viewName}-frame-${frameIndex}`,
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

describe("workspaceRuntime", () => {
  const frames = [makeFrame("camera", 0), makeFrame("camera", 1), makeFrame("camera", 2)];
  const mediaViews = { camera: frames };

  it("rebuilds tracklet child graphs so local keyframes interpolate before reload", async () => {
    const { normalizeWorkspaceRuntimeState } = await import("$lib/utils/workspaceRuntime");
    const entity = makeEntity();
    const tracklet = makeTracklet("track-1", entity, 0, 2);
    const startBBox = makeBBox("bbox-0", entity, 0, tracklet.id, [0.1, 0.2, 0.2, 0.2]);
    const endBBox = makeBBox("bbox-2", entity, 2, tracklet.id, [0.5, 0.2, 0.2, 0.2]);

    const normalized = normalizeWorkspaceRuntimeState(
      {
        annotations: [endBBox, tracklet, startBBox],
        entities: [entity],
      },
      WorkspaceType.VIDEO,
      mediaViews,
    );

    const normalizedTracklet = normalized.annotations.find(
      (annotation) => annotation.id === tracklet.id,
    ) as Tracklet | undefined;
    expect(normalizedTracklet?.ui.childs.map((annotation) => annotation.id)).toEqual([
      "bbox-0",
      "bbox-2",
    ]);
    expect(normalized.entities[0]?.ui.childs?.map((annotation) => annotation.id)).toEqual([
      "bbox-0",
      "bbox-2",
      "track-1",
    ]);

    const { results } = collectFrameAnnotations<BBox, BBox>({
      frameAnnotations: [],
      typeFilter: (annotation): annotation is BBox => annotation.is_type(BaseSchema.BBox),
      mapForDisplay: (bbox) => bbox,
      interpolateFn: boxLinearInterpolation,
      interpolationIdentity: getBBoxInterpolationIdentity,
      frameIdx: 1,
      doInterpolate: true,
      tracks: [normalizedTracklet as Tracklet],
      mViews: mediaViews,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: new Map(normalized.entities.map((item) => [item.id, item])),
    });

    expect(results).toHaveLength(1);
    expect(results[0]?.ui.frame_index).toBe(1);
    expect(results[0]?.data.frame_id).toBe("camera-frame-1");
    expect(results[0]?.ui.startRef?.id).toBe("bbox-0");
  });

  it("assigns legacy per-frame annotations to a single deterministic tracklet", async () => {
    const { normalizeWorkspaceRuntimeState } = await import("$lib/utils/workspaceRuntime");
    const entity = makeEntity();
    const wideTracklet = makeTracklet("track-wide", entity, 0, 10);
    const narrowTracklet = makeTracklet("track-narrow", entity, 2, 4);
    const legacyBBox = makeBBox("bbox-legacy", entity, 3, "");

    const normalized = normalizeWorkspaceRuntimeState(
      {
        annotations: [wideTracklet, legacyBBox, narrowTracklet],
        entities: [entity],
      },
      WorkspaceType.VIDEO,
      { camera: Array.from({ length: 11 }, (_, frameIndex) => makeFrame("camera", frameIndex)) },
    );

    const normalizedBBox = normalized.annotations.find(
      (annotation) => annotation.id === "bbox-legacy",
    ) as BBox | undefined;
    const normalizedWideTracklet = normalized.annotations.find(
      (annotation) => annotation.id === "track-wide",
    ) as Tracklet | undefined;
    const normalizedNarrowTracklet = normalized.annotations.find(
      (annotation) => annotation.id === "track-narrow",
    ) as Tracklet | undefined;

    expect(normalizedBBox?.data.tracklet_id).toBe("track-narrow");
    expect(normalizedWideTracklet?.ui.childs).toEqual([]);
    expect(normalizedNarrowTracklet?.ui.childs.map((annotation) => annotation.id)).toEqual([
      "bbox-legacy",
    ]);
  });

  it("loads VQA runtime data without crashing on orphan annotations", async () => {
    const { buildWorkspaceRuntimeData } = await import("$lib/utils/itemDataProcessing");
    const entity = makeEntity();
    const linkedBBox = makeBBox("bbox-linked", entity, 0, "", [0.1, 0.2, 0.2, 0.2]);
    linkedBBox.ui = {
      datasetItemType: WorkspaceType.IMAGE_VQA,
      displayControl: { hidden: false, editing: false, highlighted: "all" },
    };

    const orphanBBox = makeBBox("bbox-orphan", entity, 0, "", [0.5, 0.2, 0.2, 0.2]);
    orphanBBox.data.entity_id = "missing-entity";
    orphanBBox.ui = {
      datasetItemType: WorkspaceType.IMAGE_VQA,
      displayControl: { hidden: false, editing: false, highlighted: "all" },
    };

    const workspaceData: WorkspaceData = {
      item: makeItem(),
      views: { camera: makeImage("camera") },
      ui: {
        datasetId: "dataset-1",
        type: WorkspaceType.IMAGE_VQA,
      },
      entities: {
        entities: [entity],
      },
      annotations: {
        bboxes: [linkedBBox, orphanBBox],
      },
    };

    const runtime = buildWorkspaceRuntimeData(workspaceData, { main: {}, objects: {} });

    expect(runtime.annotations.map((annotation) => annotation.id)).toEqual([
      "bbox-linked",
      "bbox-orphan",
    ]);
    expect(runtime.entities[0]?.ui.childs?.map((annotation) => annotation.id)).toEqual([
      "bbox-linked",
    ]);
    const runtimeOrphanBBox = runtime.annotations.find(
      (annotation) => annotation.id === "bbox-orphan",
    ) as BBox | undefined;
    expect(runtimeOrphanBBox?.ui.top_entities).toBeUndefined();
  });

  it("keeps video track enrichment resilient when unrelated annotations have no entity chain", async () => {
    const { normalizeWorkspaceRuntimeState } = await import("$lib/utils/workspaceRuntime");
    const entity = makeEntity();
    const tracklet = makeTracklet("track-1", entity, 0, 2);
    const trackedBBox = makeBBox("bbox-tracked", entity, 0, tracklet.id, [0.1, 0.2, 0.2, 0.2]);
    const orphanBBox = makeBBox("bbox-orphan", entity, 1, "", [0.5, 0.2, 0.2, 0.2]);
    orphanBBox.data.entity_id = "missing-entity";
    orphanBBox.ui.top_entities = [];

    const normalized = normalizeWorkspaceRuntimeState(
      {
        annotations: [tracklet, trackedBBox, orphanBBox],
        entities: [entity],
      },
      WorkspaceType.VIDEO,
      mediaViews,
    );

    const normalizedTracklet = normalized.annotations.find(
      (annotation) => annotation.id === "track-1",
    ) as Tracklet | undefined;
    const normalizedOrphanBBox = normalized.annotations.find(
      (annotation) => annotation.id === "bbox-orphan",
    ) as BBox | undefined;

    expect(normalizedTracklet?.ui.childs.map((annotation) => annotation.id)).toEqual([
      "bbox-tracked",
    ]);
    expect(normalizedOrphanBBox?.ui.top_entities).toEqual([]);
    expect(normalizedOrphanBBox?.data.tracklet_id).toBe("");
  });
});
