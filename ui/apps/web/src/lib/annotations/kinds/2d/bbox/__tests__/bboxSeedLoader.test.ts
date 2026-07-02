/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { CoordsNorm } from "$lib/annotations/types.js";
import type { BBoxRow, EntityRow } from "$lib/api/annotations.js";

import { bboxSeedLoader } from "../bboxSeedLoader.js";

const CAM_FRONT: ViewInfo = { id: "CAM_FRONT_0_0", logicalName: "CAM_FRONT", width: 1600, height: 900 };

function makeContext(bboxes: BBoxRow[], entities: EntityRow[] = []): SeedLoadContext {
  const views = new Map<string, ViewInfo>();
  views.set(CAM_FRONT.id, CAM_FRONT);
  views.set(CAM_FRONT.logicalName, CAM_FRONT);
  return {
    datasetId: "ds",
    recordId: "rec_0",
    entitiesById: new Map(entities.map((e) => [e.id, e])),
    views,
    gateway: {
      listBBoxes: () => Promise.resolve(bboxes),
      listBBox3Ds: () => Promise.resolve([]),
    },
  };
}

function makeRow(overrides: Partial<BBoxRow>): BBoxRow {
  return {
    id: "b1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "CAM_FRONT_0_0",
    coords: [0.1, 0.2, 0.3, 0.4],
    format: "xywh",
    is_normalized: true,
    ...overrides,
  } as BBoxRow;
}

describe("bboxSeedLoader — coordinate normalization", () => {
  it("normalizes pixel-space xywh boxes using the view dimensions", async () => {
    const rows = await bboxSeedLoader.load(
      makeContext([makeRow({ coords: [320, 180, 160, 90], is_normalized: false })]),
    );
    const [x, y, w, h] = rows[0].geometry as CoordsNorm;
    expect(x).toBeCloseTo(320 / 1600);
    expect(y).toBeCloseTo(180 / 900);
    expect(w).toBeCloseTo(160 / 1600);
    expect(h).toBeCloseTo(90 / 900);
  });

  it("leaves already-normalized xywh boxes unchanged", async () => {
    const rows = await bboxSeedLoader.load(makeContext([makeRow({})]));
    expect(rows[0].geometry).toEqual([0.1, 0.2, 0.3, 0.4]);
  });

  it("converts pixel-space xyxy to normalized xywh", async () => {
    const rows = await bboxSeedLoader.load(
      makeContext([makeRow({ coords: [160, 90, 480, 270], format: "xyxy", is_normalized: false })]),
    );
    const [x, y, w, h] = rows[0].geometry as CoordsNorm;
    expect(x).toBeCloseTo(160 / 1600);
    expect(y).toBeCloseTo(90 / 900);
    expect(w).toBeCloseTo((480 - 160) / 1600);
    expect(h).toBeCloseTo((270 - 90) / 900);
  });

  it("converts normalized xyxy to xywh without scaling", async () => {
    const rows = await bboxSeedLoader.load(
      makeContext([makeRow({ coords: [0.1, 0.2, 0.4, 0.6], format: "xyxy" })]),
    );
    const [x, y, w, h] = rows[0].geometry as CoordsNorm;
    expect(x).toBeCloseTo(0.1);
    expect(y).toBeCloseTo(0.2);
    expect(w).toBeCloseTo(0.3);
    expect(h).toBeCloseTo(0.4);
  });
});

describe("bboxSeedLoader — view resolution", () => {
  it("resolves rows by view row id and stamps the canonical viewId", async () => {
    const rows = await bboxSeedLoader.load(makeContext([makeRow({})]));
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: "b1", viewId: "CAM_FRONT_0_0", persisted: true });
  });

  it("resolves legacy rows whose view_id is the logical name", async () => {
    const rows = await bboxSeedLoader.load(makeContext([makeRow({ id: "legacy", view_id: "CAM_FRONT" })]));
    expect(rows).toHaveLength(1);
    expect(rows[0].viewId).toBe("CAM_FRONT_0_0");
  });

  it("skips rows whose view is not displayed", async () => {
    const rows = await bboxSeedLoader.load(makeContext([makeRow({ view_id: "CAM_BACK_0_0" })]));
    expect(rows).toHaveLength(0);
  });

  it("attaches the parent entity from the record index", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const rows = await bboxSeedLoader.load(makeContext([makeRow({})], [entity]));
    expect(rows[0].entity).toBe(entity);
  });

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listBBoxes: () => Promise.reject(new Error("boom")) };
    expect(await bboxSeedLoader.load(ctx)).toEqual([]);
  });
});
