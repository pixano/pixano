/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { MASK_RESOURCE } from "../maskPayloadBuilder";
import { maskBounds } from "../maskRaster";
import { maskSeedLoader, type MaskRow } from "../maskSeedLoader";
import type { MaskGeometry } from "../maskTypes";
import {
  CORNER,
  IMAGE_SIZE,
  paintedArea,
  TRIANGLE,
  type PycocotoolsMask,
} from "./pycocotoolsMasks";
import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";
import { rleFrString } from "$lib/utils/maskUtils";

const CAM_FRONT: ViewInfo = {
  id: "CAM_FRONT_0_0",
  logicalName: "CAM_FRONT",
  width: 1600,
  height: 900,
};

function makeContext(
  rows: MaskRow[],
  entities: EntityRow[] = [],
  view: ViewInfo = CAM_FRONT,
): SeedLoadContext {
  const views = new Map<string, ViewInfo>();
  views.set(view.id, view);
  views.set(view.logicalName, view);
  return {
    datasetId: "ds",
    recordId: "rec_0",
    entitiesById: new Map(entities.map((e) => [e.id, e])),
    views,
    gateway: {
      // Resource-aware so the test also pins down *which* table the loader
      // reads: anything but "masks" comes back empty.
      listAnnotations: <TRow>(_datasetId: string, resource: string): Promise<TRow[]> =>
        Promise.resolve((resource === MASK_RESOURCE ? rows : []) as TRow[]),
    },
  };
}

function makeRow(overrides: Partial<MaskRow> = {}): MaskRow {
  return {
    id: "m1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "CAM_FRONT_0_0",
    size: [900, 1600],
    counts: "a2b1",
    ...overrides,
  };
}

describe("maskSeedLoader", () => {
  it("maps a row to a persisted local mask", async () => {
    const rows = await maskSeedLoader.load(makeContext([makeRow()]));

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "m1",
      entityId: "e1",
      kind: "mask",
      viewId: CAM_FRONT.id,
      persisted: true,
    });
  });

  it("keeps the encoding in the image grid, without normalizing", () => {
    // Unlike a bbox, a mask is tied to the pixel grid it was painted on: the
    // renderer scales it, the loader must not rewrite it.
    return maskSeedLoader.load(makeContext([makeRow()])).then((rows) => {
      expect(rows[0].geometry).toEqual({ size: [900, 1600], counts: "a2b1" });
    });
  });

  it("resolves a row whose view_id carries the logical name", async () => {
    const rows = await maskSeedLoader.load(makeContext([makeRow({ view_id: "CAM_FRONT" })]));
    expect(rows[0].viewId).toBe(CAM_FRONT.id);
  });

  it("skips rows whose view is not displayed", async () => {
    const rows = await maskSeedLoader.load(makeContext([makeRow({ view_id: "CAM_BACK" })]));
    expect(rows).toEqual([]);
  });

  it("drops the backend's empty-mask sentinel", async () => {
    // `CompressedRLE.none()` stores [0, 0] / "" — seeding it would create an
    // annotation that can never be drawn.
    const rows = await maskSeedLoader.load(makeContext([makeRow({ size: [0, 0], counts: "" })]));
    expect(rows).toEqual([]);
  });

  it("drops rows with a malformed size", async () => {
    const rows = await maskSeedLoader.load(
      makeContext([
        makeRow({ id: "bad-1", size: [900] }),
        makeRow({ id: "bad-2", size: [-1, 10] }),
        makeRow({ id: "good" }),
      ]),
    );
    expect(rows.map((r) => r.id)).toEqual(["good"]);
  });

  it("attaches the parent entity snapshot", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const rows = await maskSeedLoader.load(makeContext([makeRow()], [entity]));
    expect(rows[0].entity).toBe(entity);
  });

  it("rejects when the listing fails, rather than reading as no rows", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listAnnotations: () => Promise.reject(new Error("boom")) };
    await expect(maskSeedLoader.load(ctx)).rejects.toThrow("boom");
  });
});

describe("maskSeedLoader — a mask a segmentation job wrote", () => {
  /** The image the job segmented, as wide and as tall as the masks' grid. */
  const SEGMENTED: ViewInfo = {
    id: "image_0",
    logicalName: "image",
    width: IMAGE_SIZE[1],
    height: IMAGE_SIZE[0],
  };

  /** The row `GET /masks` serves for a mask the worker wrote, pending review. */
  function jobRow(mask: PycocotoolsMask): MaskRow {
    return {
      ...makeRow({ view_id: SEGMENTED.id, size: [...mask.size], counts: mask.counts }),
      source_type: "model",
      source_name: "segmentation",
      review_status: "pending",
    } as MaskRow;
  }

  /** Where the renderer finds the paint, to hang the mask's label on: read off the runs. */
  function paintOf(geometry: MaskGeometry) {
    const runs = rleFrString(geometry.counts);
    return { bounds: maskBounds(runs, geometry.size), area: paintedArea(runs) };
  }

  it.each([
    ["inside the image", TRIANGLE],
    ["cut by the image's top-left corner, its counts starting with an empty run", CORNER],
  ])(
    "finds pycocotools' paint on a non-square image, column by column: a mask %s",
    async (_case, mask) => {
      const [loaded] = await maskSeedLoader.load(makeContext([jobRow(mask)], [], SEGMENTED));

      // Kept as served: `[height, width]`, the string pycocotools wrote.
      expect(loaded.geometry).toEqual({ size: IMAGE_SIZE, counts: mask.counts });
      expect(loaded.review?.status).toBe("pending");
      expect(paintOf(loaded.geometry as MaskGeometry)).toEqual({
        bounds: mask.bounds,
        area: mask.area,
      });
    },
  );
});

describe("maskSeedLoader — no score", () => {
  it("reads none, whatever a row carries: the mask's schema declares no score column", async () => {
    const row = {
      ...makeRow(),
      source_type: "model",
      review_status: "pending",
      confidence: 0.5,
    } as MaskRow;
    const [mask] = await maskSeedLoader.load(makeContext([row]));

    expect(mask.review?.confidence).toBeUndefined();
    expect(mask.review?.scoreFields).toEqual([]);
  });
});
