/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  collectExactFrameAnnotations,
  collectFrameAnnotations,
  getAnnotationFrameIndex,
  getBBoxInterpolationIdentity,
  getKeypointsInterpolationIdentity,
} from "$lib/stores/frameAnnotationSelectors";
import {
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  MultiPath,
  SequenceFrame,
  Tracklet,
  WorkspaceType,
} from "$lib/types/dataset";
import { ToolType } from "$lib/types/tools";
import type { MView } from "$lib/types/workspace";

const NOW = "2026-03-29T00:00:00+00:00";
type DisplayItem = { id: string; highlight: "all" | "self" | "none" };

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
  options?: { uiFrameIndex?: number; highlighted?: "all" | "self" | "none" },
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
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      confidence: 1,
      coords: [0.1, 0.2, 0.3, 0.4],
      format: "xywh",
      is_normalized: true,
    },
  });
  bbox.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: {
      hidden: false,
      editing: false,
      highlighted: options?.highlighted ?? "self",
    },
    top_entities: [entity],
  };
  if (options?.uiFrameIndex !== undefined) {
    bbox.ui.frame_index = options.uiFrameIndex;
  } else {
    bbox.ui.frame_index = frameIndex;
  }
  return bbox;
}

function makeMask(
  id: string,
  entity: Entity,
  frameIndex: number,
  options?: { withUiFrameIndex?: boolean; highlighted?: "all" | "self" | "none" },
): Mask {
  const mask = new Mask({
    id,
    table_info: {
      name: "masks",
      group: "annotations",
      base_schema: BaseSchema.Mask,
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
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      size: [8, 8],
      counts: [2, 4, 58],
    },
  });
  mask.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: {
      hidden: false,
      editing: false,
      highlighted: options?.highlighted ?? "self",
    },
    top_entities: [entity],
  };
  if (options?.withUiFrameIndex ?? true) {
    mask.ui.frame_index = frameIndex;
  }
  return mask;
}

function makeMultiPath(id: string, entity: Entity, frameIndex: number): MultiPath {
  const multiPath = new MultiPath({
    id,
    table_info: {
      name: "multi_paths",
      group: "annotations",
      base_schema: BaseSchema.MultiPath,
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
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      coords: [0.1, 0.1, 0.3, 0.1, 0.3, 0.4],
      num_points: [3],
      is_closed: true,
    },
  });
  multiPath.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "self" },
    frame_index: frameIndex,
    top_entities: [entity],
  };
  return multiPath;
}

function makeKeypoints(
  id: string,
  entity: Entity,
  frameIndex: number,
  coords: number[] = [0.2, 0.2, 0.4, 0.2, 0.3, 0.4, 0.3, 0.6],
): Keypoints {
  const keypoints = new Keypoints({
    id,
    table_info: {
      name: "keypoints",
      group: "annotations",
      base_schema: BaseSchema.Keypoints,
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
      tracklet_id: "",
      entity_dynamic_state_id: "",
      frame_id: `camera-frame-${frameIndex}`,
      frame_index: frameIndex,
      template_id: "face",
      coords,
      states: ["visible", "visible", "visible", "visible"],
    },
  });
  keypoints.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: false, highlighted: "self" },
    frame_index: frameIndex,
    top_entities: [entity],
  };
  return keypoints;
}

function makeTracklet(id: string, entity: Entity, childs: Array<BBox | Keypoints>): Tracklet {
  const tracklet = new Tracklet({
    id,
    table_info: {
      name: "tracks",
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
      start_frame: 0,
      end_frame: 2,
      start_timestamp: 0,
      end_timestamp: 2,
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

function filterAtFrame<T extends BBox | Mask | MultiPath | Keypoints>(
  annotations: T[],
  frameIndex: number,
): T[] {
  return annotations.filter((annotation) => getAnnotationFrameIndex(annotation) === frameIndex);
}

const frames = [makeFrame("camera", 0), makeFrame("camera", 1), makeFrame("camera", 2)];
const mViews: MView = { camera: frames };

function mapDisplay<T extends BBox | Mask | MultiPath | Keypoints>(
  annotation: T,
  highlight: "all" | "self" | "none",
): DisplayItem {
  return { id: annotation.id, highlight };
}

describe("frameAnnotationSelectors", () => {
  it("shows newly appended current-frame bbox annotations immediately", () => {
    const entity = makeEntity();
    const bbox = makeBBox("bbox-1", entity, 1);

    const { results } = collectFrameAnnotations<BBox, DisplayItem>({
      frameAnnotations: filterAtFrame([bbox], 1),
      typeFilter: (annotation): annotation is BBox => annotation.is_type(BaseSchema.BBox),
      mapForDisplay: mapDisplay,
      interpolateFn: () => null,
      interpolationIdentity: getBBoxInterpolationIdentity,
      frameIdx: 1,
      doInterpolate: false,
      tracks: [],
      mViews,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["bbox-1"]);
  });

  it("shows newly appended current-frame mask annotations immediately and preserves highlight state", () => {
    const entity = makeEntity();
    const mask = makeMask("mask-1", entity, 1, {
      withUiFrameIndex: false,
      highlighted: "self",
    });

    const results = collectExactFrameAnnotations<Mask, DisplayItem>({
      frameAnnotations: filterAtFrame([mask], 1),
      mapForDisplay: mapDisplay,
      focusedEntityId: null,
      selectedToolType: ToolType.Rectangle,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["mask-1"]);
    expect(results[0]?.highlight).toBe("self");
  });

  it("shows newly appended current-frame multipath annotations immediately", () => {
    const entity = makeEntity();
    const multiPath = makeMultiPath("multipath-1", entity, 1);

    const results = collectExactFrameAnnotations<MultiPath, DisplayItem>({
      frameAnnotations: filterAtFrame([multiPath], 1),
      mapForDisplay: mapDisplay,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["multipath-1"]);
  });

  it("shows newly appended current-frame keypoints annotations immediately", () => {
    const entity = makeEntity();
    const keypoints = makeKeypoints("keypoints-1", entity, 1);

    const { results } = collectFrameAnnotations<Keypoints, DisplayItem>({
      frameAnnotations: filterAtFrame([keypoints], 1),
      typeFilter: (annotation): annotation is Keypoints => annotation.is_type(BaseSchema.Keypoints),
      mapForDisplay: mapDisplay,
      interpolateFn: () => null,
      interpolationIdentity: getKeypointsInterpolationIdentity,
      frameIdx: 1,
      doInterpolate: false,
      tracks: [],
      mViews,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["keypoints-1"]);
  });

  it("prefers exact current-frame bbox annotations over interpolated tracklet ghosts", () => {
    const entity = makeEntity();
    const exact = makeBBox("bbox-current", entity, 1);
    const tracklet = makeTracklet("track-1", entity, [
      makeBBox("bbox-start", entity, 0, { highlighted: "none" }),
      makeBBox("bbox-end", entity, 2, { highlighted: "none" }),
    ]);

    const { results } = collectFrameAnnotations<BBox, DisplayItem>({
      frameAnnotations: filterAtFrame([exact], 1),
      typeFilter: (annotation): annotation is BBox => annotation.is_type(BaseSchema.BBox),
      mapForDisplay: mapDisplay,
      interpolateFn: () => ({ id: "bbox-interpolated", highlight: "none" }),
      interpolationIdentity: getBBoxInterpolationIdentity,
      frameIdx: 1,
      doInterpolate: true,
      tracks: [tracklet],
      mViews,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["bbox-current"]);
  });

  it("prefers exact current-frame keypoints annotations over interpolated tracklet ghosts", () => {
    const entity = makeEntity();
    const exact = makeKeypoints("keypoints-current", entity, 1);
    const tracklet = makeTracklet("track-1", entity, [
      makeKeypoints("keypoints-start", entity, 0, [0.1, 0.1, 0.2, 0.1, 0.15, 0.2, 0.15, 0.3]),
      makeKeypoints("keypoints-end", entity, 2, [0.3, 0.1, 0.4, 0.1, 0.35, 0.2, 0.35, 0.3]),
    ]);

    const { results } = collectFrameAnnotations<Keypoints, DisplayItem>({
      frameAnnotations: filterAtFrame([exact], 1),
      typeFilter: (annotation): annotation is Keypoints => annotation.is_type(BaseSchema.Keypoints),
      mapForDisplay: mapDisplay,
      interpolateFn: () => ({ id: "keypoints-interpolated", highlight: "none" }),
      interpolationIdentity: getKeypointsInterpolationIdentity,
      frameIdx: 1,
      doInterpolate: true,
      tracks: [tracklet],
      mViews,
      focusedEntityId: null,
      selectedToolType: ToolType.Pan,
      entitiesById: null,
    });

    expect(results.map((annotation) => annotation.id)).toEqual(["keypoints-current"]);
  });
});
