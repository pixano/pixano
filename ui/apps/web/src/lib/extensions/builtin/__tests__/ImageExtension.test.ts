/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

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

function makeGateway(image: CalibratedImageResponse | null): DatasetGateway {
  return {
    getDataset: () => Promise.resolve(null as never),
    listEntities: () => Promise.resolve([]),
    loadImageByLogicalName: () => Promise.resolve(image),
    listBBoxes: () => Promise.resolve([]),
    loadPointCloudByLogicalName: () => Promise.resolve(null),
    listBBox3Ds: () => Promise.resolve([]),
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  };
}

function makeCtx(image: CalibratedImageResponse | null, viewName = "CAM_FRONT") {
  return {
    datasetId: "ds",
    recordId: "rec_0",
    viewName,
    viewDef: { base: "Image" },
    entitiesById: new Map(),
    gateway: makeGateway(image),
  };
}

// ─── Tests ────────────────────────────────────────────────────────────────────
// Annotation row mapping (normalization, view resolution) is the seed
// loaders' job — see kinds/2d/bbox/__tests__/bboxSeedLoader.test.ts.

describe("ImageExtension.addRecordSeed", () => {
  it("describes the claimed view for the seed loaders (annotations are not fetched here)", async () => {
    const seed = await ImageExtension.config.addRecordSeed!(makeCtx(IMAGE));

    expect(seed).not.toBeNull();
    expect(seed!.view).toEqual({
      id: "CAM_FRONT_0_0",
      logicalName: "CAM_FRONT",
      width: 1600,
      height: 900,
    });
    expect(seed!.options).toMatchObject({
      viewId: "CAM_FRONT_0_0",
      viewName: "CAM_FRONT",
      imageWidth: 1600,
      imageHeight: 900,
    });
    expect(seed!.data).toEqual({ imageUrl: "/cam.jpg" });
  });

  it("still claims the view when no image row is found", async () => {
    const seed = await ImageExtension.config.addRecordSeed!(makeCtx(null));

    expect(seed).not.toBeNull();
    expect(seed!.view).toEqual({ id: "", logicalName: "CAM_FRONT", width: 0, height: 0 });
  });

  it("returns null for non-Image view bases", async () => {
    const ctx = { ...makeCtx(IMAGE, "points"), viewDef: { base: "PointCloud" } };
    const seed = await ImageExtension.config.addRecordSeed!(ctx);
    expect(seed).toBeNull();
  });
});
