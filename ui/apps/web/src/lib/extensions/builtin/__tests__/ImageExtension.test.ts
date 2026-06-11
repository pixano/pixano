/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import type { BBoxRow } from "$lib/api/annotations.js";
import type { CalibratedImageResponse } from "$lib/api/restTypes.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";

// ImageExtension references ImageWidget.svelte which imports Konva (requires native canvas).
// Mock the component so this unit test stays pure JS.
vi.mock("$lib/components/widgets/image/ImageWidget.svelte", () => ({ default: {} }));

import { ImageExtension } from "../ImageExtension.js";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const IMAGE: CalibratedImageResponse = {
  id: "CAM_FRONT_0_0",
  record_id: "rec_0",
  src: "/cam.jpg",
  width: 1600,
  height: 900,
  f: null,
  c: null,
  distortion: null,
  extrinsic_matrix: null,
  ego_to_world: null,
};

function makeGateway(image: CalibratedImageResponse | null, bboxes: BBoxRow[]): DatasetGateway {
  return {
    getDataset: () => Promise.resolve(null as never),
    listEntities: () => Promise.resolve([]),
    loadImageByLogicalName: () => Promise.resolve(image),
    listBBoxes: () => Promise.resolve(bboxes),
    loadPointCloudByLogicalName: () => Promise.resolve(null),
    listBBox3Ds: () => Promise.resolve([]),
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  };
}

function makeCtx(bboxes: BBoxRow[], viewName = "CAM_FRONT") {
  return {
    datasetId: "ds",
    recordId: "rec_0",
    viewName,
    viewDef: { base: "Image" },
    entitiesById: new Map(),
    gateway: makeGateway(IMAGE, bboxes),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("ImageExtension.addRecordSeed — bbox normalization", () => {
  it("normalizes pixel-space xywh boxes using image dimensions", async () => {
    const bbox: BBoxRow = {
      id: "b1",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT_0_0",
      coords: [320, 180, 160, 90],
      format: "xywh",
      is_normalized: false,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([bbox]));

    expect(seed).not.toBeNull();
    const [x, y, w, h] = seed!.storage!.bboxes![0].coordsNorm;
    expect(x).toBeCloseTo(320 / 1600);
    expect(y).toBeCloseTo(180 / 900);
    expect(w).toBeCloseTo(160 / 1600);
    expect(h).toBeCloseTo(90 / 900);
  });

  it("leaves already-normalized xywh boxes unchanged", async () => {
    const bbox: BBoxRow = {
      id: "b2",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT_0_0",
      coords: [0.1, 0.2, 0.3, 0.4],
      format: "xywh",
      is_normalized: true,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([bbox]));

    expect(seed!.storage!.bboxes![0].coordsNorm).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it("converts pixel-space xyxy to normalized xywh", async () => {
    const bbox: BBoxRow = {
      id: "b3",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT_0_0",
      coords: [160, 90, 480, 270],
      format: "xyxy",
      is_normalized: false,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([bbox]));

    const [x, y, w, h] = seed!.storage!.bboxes![0].coordsNorm;
    expect(x).toBeCloseTo(160 / 1600);
    expect(y).toBeCloseTo(90 / 900);
    expect(w).toBeCloseTo((480 - 160) / 1600);
    expect(h).toBeCloseTo((270 - 90) / 900);
  });

  it("converts normalized xyxy to xywh without scaling", async () => {
    const bbox: BBoxRow = {
      id: "b4",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT_0_0",
      coords: [0.1, 0.2, 0.4, 0.6],
      format: "xyxy",
      is_normalized: true,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([bbox]));

    const [x, y, w, h] = seed!.storage!.bboxes![0].coordsNorm;
    expect(x).toBeCloseTo(0.1);
    expect(y).toBeCloseTo(0.2);
    expect(w).toBeCloseTo(0.3);
    expect(h).toBeCloseTo(0.4);
  });

  it("filters boxes by image row id (new NuScenes format)", async () => {
    const matching: BBoxRow = {
      id: "match",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT_0_0",
      coords: [0.1, 0.1, 0.2, 0.2],
      format: "xywh",
      is_normalized: true,
    };
    const other: BBoxRow = {
      id: "other",
      record_id: "rec_0",
      entity_id: "e2",
      view_id: "CAM_BACK_0_0",
      coords: [0.3, 0.3, 0.1, 0.1],
      format: "xywh",
      is_normalized: true,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([matching, other]));

    expect(seed!.storage!.bboxes).toHaveLength(1);
    expect(seed!.storage!.bboxes![0].id).toBe("match");
  });

  it("filters boxes by logical view name (legacy format)", async () => {
    const matching: BBoxRow = {
      id: "legacy",
      record_id: "rec_0",
      entity_id: "e1",
      view_id: "CAM_FRONT",
      coords: [0.1, 0.1, 0.2, 0.2],
      format: "xywh",
      is_normalized: true,
    };

    const seed = await ImageExtension.config.addRecordSeed!(makeCtx([matching]));

    expect(seed!.storage!.bboxes).toHaveLength(1);
    expect(seed!.storage!.bboxes![0].id).toBe("legacy");
  });

  it("returns empty bboxes when no image is found for the view", async () => {
    const ctx = {
      datasetId: "ds",
      recordId: "rec_0",
      viewName: "CAM_FRONT",
      viewDef: { base: "Image" },
      entitiesById: new Map(),
      gateway: makeGateway(null, []),
    };

    const seed = await ImageExtension.config.addRecordSeed!(ctx);

    expect(seed!.storage!.bboxes).toHaveLength(0);
  });

  it("returns null for non-Image view bases", async () => {
    const ctx = {
      datasetId: "ds",
      recordId: "rec_0",
      viewName: "points",
      viewDef: { base: "PointCloud" },
      entitiesById: new Map(),
      gateway: makeGateway(IMAGE, []),
    };

    const seed = await ImageExtension.config.addRecordSeed!(ctx);

    expect(seed).toBeNull();
  });
});
