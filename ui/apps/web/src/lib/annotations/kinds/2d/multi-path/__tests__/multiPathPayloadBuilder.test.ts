/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildMultiPathCreate, buildMultiPathUpdate } from "../multiPathPayloadBuilder";
import type { MultiPathGeometry } from "../multiPathTypes";
import type { ResourceMutation } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

/** Two rings: a 4-point one and a 3-point one. */
const POLYGON: MultiPathGeometry = {
  coords: [0.1, 0.1, 0.4, 0.1, 0.4, 0.4, 0.1, 0.4, 0.6, 0.6, 0.8, 0.6, 0.7, 0.9],
  numPoints: [4, 3],
  isClosed: true,
};

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildMultiPathCreate", () => {
  it("returns two mutations in (entity, multi-path) order", () => {
    const { mutations } = buildMultiPathCreate(CTX, POLYGON);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("multi-paths");
  });

  it("renames the geometry fields to the backend's snake_case columns", () => {
    const body = bodyOf(buildMultiPathCreate(CTX, POLYGON).mutations[1]);

    expect(body.num_points).toEqual([4, 3]);
    expect(body.is_closed).toBe(true);
    expect(body).not.toHaveProperty("numPoints");
    expect(body).not.toHaveProperty("isClosed");
  });

  it("keeps sum(num_points) * 2 equal to the coord count", () => {
    // The backend validator rejects any disagreement outright.
    const body = bodyOf(buildMultiPathCreate(CTX, POLYGON).mutations[1]);
    const coords = body.coords as number[];
    const numPoints = body.num_points as number[];

    expect(numPoints.reduce((a, b) => a + b, 0) * 2).toBe(coords.length);
  });

  it("carries an open polyline through with is_closed false", () => {
    const polyline: MultiPathGeometry = {
      coords: [0.1, 0.1, 0.5, 0.5],
      numPoints: [2],
      isClosed: false,
    };
    const body = bodyOf(buildMultiPathCreate(CTX, polyline).mutations[1]);

    expect(body.is_closed).toBe(false);
    expect(body.num_points).toEqual([2]);
  });

  it("omits confidence, which MultiPath has no column for", () => {
    const body = bodyOf(buildMultiPathCreate(CTX, POLYGON).mutations[1]);
    expect(body).not.toHaveProperty("confidence");
  });

  it("carries the single-frame linkage columns", () => {
    const body = bodyOf(buildMultiPathCreate(CTX, POLYGON).mutations[1]);

    expect(body.frame_id).toBe("view-1");
    expect(body.frame_index).toBe(-1);
    expect(body.tracklet_id).toBe("");
    expect(body.entity_dynamic_state_id).toBe("");
  });

  it("copies the arrays rather than aliasing the caller's", () => {
    const geometry: MultiPathGeometry = { ...POLYGON, coords: [...POLYGON.coords] };
    const body = bodyOf(buildMultiPathCreate(CTX, geometry).mutations[1]);

    expect(body.coords).not.toBe(geometry.coords);
    expect(body.num_points).not.toBe(geometry.numPoints);
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildMultiPathCreate(CTX, POLYGON, {
      entityId: "existing-1",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-1");
  });
});

describe("buildMultiPathUpdate", () => {
  it("is a subset of the create body with identical values (D9)", () => {
    // `commitGeometryEdit` patches a still-pending create with the update body,
    // so any field they disagree on would silently corrupt the queued create.
    const ids = { entityId: "e-1", annotationId: "p-1" };
    const createBody = bodyOf(buildMultiPathCreate(CTX, POLYGON, ids).mutations[1]);
    const updateBody = buildMultiPathUpdate(CTX, ids.annotationId, ids.entityId, POLYGON);

    for (const [key, value] of Object.entries(updateBody)) {
      expect(createBody).toHaveProperty(key, value);
    }
  });
});
