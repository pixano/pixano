/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { toRawAnnotation } from "$lib/api/adapters";
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
  Mask,
  SequenceFrame,
  Tracklet,
  WorkspaceType,
} from "$lib/types/dataset";
import { ToolType } from "$lib/types/tools";
import type { WorkspaceData } from "$lib/types/workspace";
import { createTypedAnnotation } from "$lib/utils/domainFactories";
import { boxLinearInterpolation } from "$lib/utils/interpolation";
import type { MaskBounds } from "$lib/utils/maskUtils";

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

const DEFAULT_IMAGE_SIDE = 100;

function makeImage(
  viewName = "camera",
  width = DEFAULT_IMAGE_SIDE,
  height = DEFAULT_IMAGE_SIDE,
): Image {
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
      width,
      height,
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
      tracks: [normalizedTracklet],
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

/**
 * Masks as the backend stores them: encoded by pycocotools
 * (`CompressedRLE.from_mask`), `counts` served as a utf-8 string, on an image
 * wider than tall. Produced by:
 *
 *   import numpy as np
 *   from pycocotools import mask as mask_api
 *   from pixano.features import CompressedRLE
 *
 *   triangle = np.zeros((24, 40), dtype=np.uint8)
 *   for c in range(9, 29):
 *       triangle[5 : 5 + (c - 9) // 2 + 1, c] = 1
 *   corner = np.zeros((24, 40), dtype=np.uint8)
 *   corner[0:7, 0:12] = 1
 *
 *   for m in (triangle, corner):
 *       rle = CompressedRLE.from_mask(m).model_dump()
 *       raw = mask_api.encode(np.asfortranarray(m))
 *       print(rle["counts"], mask_api.toBbox(raw), mask_api.area(raw))
 *
 * `bounds` and `area` are pycocotools' own reading (`toBbox`, `area`), so they
 * are the expected values, not a second decode of ours.
 */
interface PycocotoolsMask {
  counts: string;
  bounds: MaskBounds;
  area: number;
}

/** `[height, width]` of the image the masks were segmented on. */
const SEGMENTED_IMAGE_SIZE: [number, number] = [24, 40];

/** A triangle: run lengths that change from column to column, negative differences encoded. */
const TRIANGLE: PycocotoolsMask = {
  counts: "m61g0001O001O001O001O001O001O001O001O001O0S8",
  bounds: { x: 9, y: 5, width: 20, height: 10 },
  area: 110,
};

/** An object cut by the image's top-left corner: its counts start with an empty run, a `0`. */
const CORNER: PycocotoolsMask = {
  counts: "07a0000000000000000000000Pe0",
  bounds: { x: 0, y: 0, width: 12, height: 7 },
  area: 84,
};

/** How many pixels a run-length list paints: every second run, from the second. */
function paintedArea(runs: number[]): number {
  return runs.reduce((sum, run, index) => (index % 2 === 1 ? sum + run : sum), 0);
}

describe("workspaceRuntime, a mask the backend stored", () => {
  it.each([
    ["inside the image", TRIANGLE],
    ["cut by the image's top-left corner", CORNER],
  ])(
    "finds pycocotools' paint on a non-square image, column by column: a mask %s",
    async (_case, mask) => {
      const { normalizeWorkspaceRuntimeState } = await import("$lib/utils/workspaceRuntime");
      const [height, width] = SEGMENTED_IMAGE_SIZE;
      const image = makeImage("camera", width, height);
      const entity = makeEntity();
      // The row `GET /masks` serves, through the loader's own adapter and factory.
      const row = {
        id: "mask-1",
        record_id: "item-1",
        entity_id: entity.id,
        view_id: image.id,
        size: [...SEGMENTED_IMAGE_SIZE],
        counts: mask.counts,
        source_type: "model",
      };
      const loaded = createTypedAnnotation(
        toRawAnnotation(row, new Map([[image.id, image.data.view_name]]), "masks"),
      );
      expect(loaded).toBeInstanceOf(Mask);

      const normalized = normalizeWorkspaceRuntimeState(
        { annotations: [loaded as Mask], entities: [entity] },
        WorkspaceType.IMAGE,
        { camera: image },
      );

      const normalizedMask = normalized.annotations[0] as Mask;
      expect(normalizedMask.data.view_name).toBe("camera");
      expect(normalizedMask.ui.bounds).toEqual(mask.bounds);
      expect(paintedArea(normalizedMask.data.counts as number[])).toBe(mask.area);
      expect(normalized.entities[0]?.ui.childs?.map((child) => child.id)).toEqual(["mask-1"]);
    },
  );
});
