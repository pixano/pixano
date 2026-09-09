/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { MASK_RESOURCE } from "../maskPayloadBuilder";
import { maskSeedLoader, type MaskRow } from "../maskSeedLoader";
import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";

const CAM_FRONT: ViewInfo = {
  id: "CAM_FRONT_0_0",
  logicalName: "CAM_FRONT",
  width: 1600,
  height: 900,
};

function makeContext(rows: MaskRow[], entities: EntityRow[] = []): SeedLoadContext {
  const views = new Map<string, ViewInfo>();
  views.set(CAM_FRONT.id, CAM_FRONT);
  views.set(CAM_FRONT.logicalName, CAM_FRONT);
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

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listAnnotations: () => Promise.reject(new Error("boom")) };
    expect(await maskSeedLoader.load(ctx)).toEqual([]);
  });
});
