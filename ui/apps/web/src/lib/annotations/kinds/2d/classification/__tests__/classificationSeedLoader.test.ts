/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { CLASSIFICATION_RESOURCE } from "../classificationPayloadBuilder";
import { classificationSeedLoader, type ClassificationRow } from "../classificationSeedLoader";
import type { LocalClassification } from "$lib/annotations/annotationCollection.svelte.js";
import type { SeedLoadContext, ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";

const CAM_FRONT: ViewInfo = {
  id: "CAM_FRONT_0_0",
  logicalName: "CAM_FRONT",
  width: 1600,
  height: 900,
};

function makeContext(rows: ClassificationRow[], entities: EntityRow[] = []): SeedLoadContext {
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
        Promise.resolve((resource === CLASSIFICATION_RESOURCE ? rows : []) as TRow[]),
    },
  };
}

function makeRow(overrides: Partial<ClassificationRow> = {}): ClassificationRow {
  return {
    id: "c1",
    record_id: "rec_0",
    entity_id: "e1",
    view_id: "CAM_FRONT_0_0",
    labels: ["beach"],
    confidences: [1],
    ...overrides,
  };
}

async function loadOne(row: Partial<ClassificationRow>): Promise<LocalClassification[]> {
  return (await classificationSeedLoader.load(
    makeContext([makeRow(row)]),
  )) as LocalClassification[];
}

describe("classificationSeedLoader", () => {
  it("maps a row to a persisted local classification", async () => {
    const rows = await loadOne({});

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "c1",
      entityId: "e1",
      kind: "classification",
      viewId: CAM_FRONT.id,
      persisted: true,
    });
  });

  it("carries the labels through without touching them", async () => {
    const rows = await loadOne({ labels: ["beach", "sunset"], confidences: [1, 0.8] });

    expect(rows[0].geometry).toEqual({
      labels: ["beach", "sunset"],
      confidences: [1, 0.8],
    });
  });

  it("skips rows whose view is not displayed", async () => {
    const rows = await loadOne({ view_id: "CAM_BACK" });
    expect(rows).toEqual([]);
  });

  it("drops rows that break the backend's own invariant", async () => {
    // A row can also arrive from an import that bypassed the API; a mismatch
    // would pair a label with someone else's confidence.
    const rows = await classificationSeedLoader.load(
      makeContext([
        makeRow({ id: "count-mismatch", labels: ["a", "b"], confidences: [1] }),
        makeRow({ id: "no-labels", labels: [], confidences: [] }),
        makeRow({ id: "empty-label", labels: [""], confidences: [1] }),
        makeRow({ id: "good" }),
      ]),
    );

    expect(rows.map((r) => r.id)).toEqual(["good"]);
  });

  it("attaches the parent entity snapshot", async () => {
    const entity = { id: "e1", record_id: "rec_0" } as EntityRow;
    const rows = await classificationSeedLoader.load(makeContext([makeRow()], [entity]));
    expect(rows[0].entity).toBe(entity);
  });

  it("returns empty when the listing fails", async () => {
    const ctx = makeContext([]);
    ctx.gateway = { ...ctx.gateway, listAnnotations: () => Promise.reject(new Error("boom")) };
    expect(await classificationSeedLoader.load(ctx)).toEqual([]);
  });
});
