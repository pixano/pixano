/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { MULTI_PATH_RESOURCE } from "../multiPathPayloadBuilder";
import { multiPathSeedLoader, type MultiPathRow } from "../multiPathSeedLoader";
import type { LocalMultiPath } from "$lib/annotations/annotationCollection.svelte.js";
import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";

const CAM_FRONT: ViewInfo = {
  id: "CAM_FRONT_0_0",
  logicalName: "CAM_FRONT",
  width: 1600,
  height: 900,
};

function makeContext(rows: MultiPathRow[], entities: EntityRow[] = []): SeedLoadContext {
  const views = new Map<string, ViewInfo>();
  views.set(CAM_FRONT.id, CAM_FRONT);
  views.set(CAM_FRONT.logicalName, CAM_FRONT);
  return {
    datasetId: "ds",
    recordId: "rec_0",
    entitiesById: new Map(entities.map((e) => [e.id, e])),
    views,
    gateway: {
      listAnnotations: <TRow>(_datasetId: string, resource: string): Promise<TRow[]> =>
        Promise.resolve((resource === MULTI_PATH_RESOURCE ? rows : []) as TRow[]),
    },
  };
}

function makeRow(overrides: Partial<MultiPathRow> = {}): MultiPathRow {
  return {
    id: "p1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "CAM_FRONT_0_0",
    coords: [0.1, 0.1, 0.4, 0.1, 0.4, 0.4],
    num_points: [3],
    is_closed: true,
    ...overrides,
  };
}

async function loadOne(row: Partial<MultiPathRow>): Promise<LocalMultiPath[]> {
  return (await multiPathSeedLoader.load(makeContext([makeRow(row)]))) as LocalMultiPath[];
}

describe("multiPathSeedLoader", () => {
  it("maps a row to a persisted local path", async () => {
    const rows = await loadOne({});

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "p1",
      entityId: "e1",
      kind: "multi_path",
      viewId: CAM_FRONT.id,
      persisted: true,
    });
  });

  it("renames the snake_case columns onto the geometry", async () => {
    const rows = await loadOne({});

    expect(rows[0].geometry).toEqual({
      coords: [0.1, 0.1, 0.4, 0.1, 0.4, 0.4],
      numPoints: [3],
      isClosed: true,
    });
  });

  it("keeps a multi-part polygon's sub-path lengths", async () => {
    const rows = await loadOne({
      coords: [0.1, 0.1, 0.4, 0.1, 0.4, 0.4, 0.6, 0.6, 0.8, 0.6, 0.7, 0.9],
      num_points: [3, 3],
    });

    expect(rows[0].geometry.numPoints).toEqual([3, 3]);
  });

  it("accepts a 2-point polyline, which is too short for a polygon", async () => {
    const rows = await loadOne({ coords: [0.1, 0.1, 0.5, 0.5], num_points: [2], is_closed: false });
    expect(rows).toHaveLength(1);
  });

  it("skips rows whose view is not displayed", async () => {
    const rows = await loadOne({ view_id: "CAM_BACK" });
    expect(rows).toEqual([]);
  });

  it("drops rows that break the backend's own invariants", async () => {
    // A row can also arrive from an import that bypassed the API, so the loader
    // re-checks rather than trusting the write path.
    const rows = await multiPathSeedLoader.load(
      makeContext([
        // sum(num_points) * 2 !== coords.length
        makeRow({ id: "count-mismatch", num_points: [2] }),
        // odd coord count
        makeRow({ id: "odd", coords: [0.1, 0.1, 0.4], num_points: [1] }),
        // a closed ring needs 3 points
        makeRow({ id: "short-ring", coords: [0.1, 0.1, 0.5, 0.5], num_points: [2] }),
        // coordinates must be normalized
        makeRow({ id: "out-of-range", coords: [1.5, 0.1, 0.4, 0.1, 0.4, 0.4] }),
        makeRow({ id: "negative", coords: [-0.1, 0.1, 0.4, 0.1, 0.4, 0.4] }),
        makeRow({ id: "good" }),
      ]),
    );

    expect(rows.map((r) => r.id)).toEqual(["good"]);
  });

  it("attaches the parent entity snapshot", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const rows = await multiPathSeedLoader.load(makeContext([makeRow()], [entity]));
    expect(rows[0].entity).toBe(entity);
  });

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listAnnotations: () => Promise.reject(new Error("boom")) };
    expect(await multiPathSeedLoader.load(ctx)).toEqual([]);
  });
});
