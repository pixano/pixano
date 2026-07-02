/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { BBox3DGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import type { SeedLoadContext } from "$lib/annotations/seedLoaders.js";
import type { BBox3DRow, EntityRow } from "$lib/api/annotations.js";

import { bbox3dSeedLoader } from "../bbox3dSeedLoader.js";

function makeContext(rows: BBox3DRow[], entities: EntityRow[] = []): SeedLoadContext {
  return {
    datasetId: "ds",
    recordId: "rec_0",
    entitiesById: new Map(entities.map((e) => [e.id, e])),
    views: new Map(),
    gateway: {
      listBBoxes: () => Promise.resolve([]),
      listBBox3Ds: () => Promise.resolve(rows),
    },
  };
}

function makeRow(overrides: Partial<BBox3DRow> = {}): BBox3DRow {
  return {
    id: "box-1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "",
    coords: [1, 2, 3, 4, 5, 6],
    format: "xyzwhd",
    rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    is_normalized: false,
    ...overrides,
  } as BBox3DRow;
}

describe("bbox3dSeedLoader", () => {
  it("maps rows to record-scoped persisted annotations regardless of displayed views", async () => {
    // `views` is empty: a record-scoped kind is kept even when no view matches.
    const anns = await bbox3dSeedLoader.load(makeContext([makeRow()]));
    expect(anns).toHaveLength(1);
    expect(anns[0]).toMatchObject({ id: "box-1", entityId: "e1", kind: "bbox3d", persisted: true });
    expect(anns[0].geometry as BBox3DGeometry).toEqual({
      coords: [1, 2, 3, 4, 5, 6],
      format: "xyzwhd",
      rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    });
  });

  it("carries the row's view_id through (often empty for scene-level boxes)", async () => {
    expect((await bbox3dSeedLoader.load(makeContext([makeRow({ view_id: "" })])))[0].viewId).toBe("");
    expect(
      (await bbox3dSeedLoader.load(makeContext([makeRow({ view_id: "lidar-top" })])))[0].viewId,
    ).toBe("lidar-top");
  });

  it("preserves the xyzxyz format when the backend sends it", async () => {
    const anns = await bbox3dSeedLoader.load(makeContext([makeRow({ format: "xyzxyz" })]));
    expect((anns[0].geometry as BBox3DGeometry).format).toBe("xyzxyz");
  });

  it("attaches the parent entity from the record index", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const anns = await bbox3dSeedLoader.load(makeContext([makeRow()], [entity]));
    expect(anns[0].entity).toBe(entity);
  });

  it("leaves entity undefined when entity_id is empty", async () => {
    const anns = await bbox3dSeedLoader.load(makeContext([makeRow({ entity_id: "" })]));
    expect(anns[0].entity).toBeUndefined();
  });

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listBBox3Ds: () => Promise.reject(new Error("boom")) };
    expect(await bbox3dSeedLoader.load(ctx)).toEqual([]);
  });
});
