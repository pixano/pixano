/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { KEYPOINTS_RESOURCE } from "../keypointsPayloadBuilder";
import { keypointsSeedLoader, type KeypointsRow } from "../keypointsSeedLoader";
import type { LocalKeypoints } from "$lib/annotations/annotationCollection.svelte.js";
import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";

const CAM_FRONT: ViewInfo = {
  id: "CAM_FRONT_0_0",
  logicalName: "CAM_FRONT",
  width: 1600,
  height: 900,
};

function makeContext(rows: KeypointsRow[], entities: EntityRow[] = []): SeedLoadContext {
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
        Promise.resolve((resource === KEYPOINTS_RESOURCE ? rows : []) as TRow[]),
    },
  };
}

function makeRow(overrides: Partial<KeypointsRow> = {}): KeypointsRow {
  return {
    id: "k1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "CAM_FRONT_0_0",
    template_id: "face",
    coords: [0.3, 0.25, 0.6, 0.25, 0.45, 0.45, 0.45, 0.75],
    states: ["visible", "visible", "invisible", "hidden"],
    ...overrides,
  };
}

describe("keypointsSeedLoader", () => {
  it("maps a row to a persisted local skeleton", async () => {
    const rows = await keypointsSeedLoader.load(makeContext([makeRow()]));

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "k1",
      entityId: "e1",
      kind: "keypoints",
      viewId: CAM_FRONT.id,
      persisted: true,
    });
  });

  it("keeps coords normalized, as stored", async () => {
    const rows = await keypointsSeedLoader.load(makeContext([makeRow()]));

    expect(rows[0].geometry).toEqual({
      templateId: "face",
      coords: [0.3, 0.25, 0.6, 0.25, 0.45, 0.45, 0.45, 0.75],
      states: ["visible", "visible", "invisible", "hidden"],
    });
  });

  it("resolves a row whose view_id carries the logical name", async () => {
    const rows = await keypointsSeedLoader.load(makeContext([makeRow({ view_id: "CAM_FRONT" })]));
    expect(rows[0].viewId).toBe(CAM_FRONT.id);
  });

  it("skips rows whose view is not displayed", async () => {
    const rows = await keypointsSeedLoader.load(makeContext([makeRow({ view_id: "CAM_BACK" })]));
    expect(rows).toEqual([]);
  });

  it("keeps a row whose template is unknown to the registry", async () => {
    // Only the bones and labels are lost; the points themselves are still data.
    // `load` is declared over the kind-agnostic `LocalAnnotation`, whose
    // geometry is `unknown`, so narrow it to read a kind-specific field.
    const rows = (await keypointsSeedLoader.load(
      makeContext([makeRow({ template_id: "alien" })]),
    )) as LocalKeypoints[];
    expect(rows).toHaveLength(1);
    expect(rows[0].geometry.templateId).toBe("alien");
  });

  it("drops rows that break the backend's own invariants", async () => {
    // A row can also arrive from an import that bypassed the API, so the loader
    // re-checks rather than trusting the write path.
    const rows = await keypointsSeedLoader.load(
      makeContext([
        makeRow({ id: "odd-coords", coords: [0.1, 0.2, 0.3], states: ["visible"] }),
        makeRow({ id: "state-mismatch", states: ["visible"] }),
        makeRow({ id: "bad-state", states: ["visible", "visible", "visible", "elsewhere"] }),
        makeRow({ id: "negative", coords: [-0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] }),
        makeRow({ id: "empty", coords: [], states: [] }),
        makeRow({ id: "good" }),
      ]),
    );

    expect(rows.map((r) => r.id)).toEqual(["good"]);
  });

  it("attaches the parent entity snapshot", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const rows = await keypointsSeedLoader.load(makeContext([makeRow()], [entity]));
    expect(rows[0].entity).toBe(entity);
  });

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listAnnotations: () => Promise.reject(new Error("boom")) };
    expect(await keypointsSeedLoader.load(ctx)).toEqual([]);
  });
});
