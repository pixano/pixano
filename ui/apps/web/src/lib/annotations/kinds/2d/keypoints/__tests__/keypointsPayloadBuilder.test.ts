/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildKeypointsCreate, buildKeypointsUpdate } from "../keypointsPayloadBuilder";
import type { KeypointsGeometry } from "../keypointsTypes";
import type { ResourceMutation } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

const GEOMETRY: KeypointsGeometry = {
  templateId: "face",
  coords: [0.3, 0.25, 0.6, 0.25, 0.45, 0.45, 0.45, 0.75],
  states: ["visible", "visible", "invisible", "visible"],
};

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildKeypointsCreate", () => {
  it("returns two mutations in (entity, keypoints) order", () => {
    const { mutations } = buildKeypointsCreate(CTX, GEOMETRY);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("keypoints");
  });

  it("sends the template, coords and states through untouched", () => {
    const body = bodyOf(buildKeypointsCreate(CTX, GEOMETRY).mutations[1]);

    expect(body.template_id).toBe("face");
    expect(body.coords).toEqual([0.3, 0.25, 0.6, 0.25, 0.45, 0.45, 0.45, 0.75]);
    expect(body.states).toEqual(["visible", "visible", "invisible", "visible"]);
  });

  it("keeps one state per point, as the backend validator requires", () => {
    const body = bodyOf(buildKeypointsCreate(CTX, GEOMETRY).mutations[1]);
    const coords = body.coords as number[];
    const states = body.states as string[];

    expect(states).toHaveLength(coords.length / 2);
  });

  it("omits confidence, which KeyPoints has no column for", () => {
    // BBox carries `confidence`; the keypoints schema does not, and the backend
    // rejects unknown fields.
    const body = bodyOf(buildKeypointsCreate(CTX, GEOMETRY).mutations[1]);
    expect(body).not.toHaveProperty("confidence");
  });

  it("carries the single-frame linkage columns", () => {
    const body = bodyOf(buildKeypointsCreate(CTX, GEOMETRY).mutations[1]);

    expect(body.frame_id).toBe("view-1");
    expect(body.frame_index).toBe(-1);
    expect(body.tracklet_id).toBe("");
    expect(body.entity_dynamic_state_id).toBe("");
  });

  it("copies coords and states rather than aliasing the caller's arrays", () => {
    // The collection keeps the geometry object; a body holding the same array
    // reference would mutate the queued payload on the next edit.
    const geometry: KeypointsGeometry = { ...GEOMETRY, coords: [...GEOMETRY.coords] };
    const body = bodyOf(buildKeypointsCreate(CTX, geometry).mutations[1]);

    expect(body.coords).not.toBe(geometry.coords);
    expect(body.states).not.toBe(geometry.states);
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildKeypointsCreate(CTX, GEOMETRY, {
      entityId: "existing-1",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-1");
  });
});

describe("buildKeypointsUpdate", () => {
  it("is a subset of the create body with identical values (D9)", () => {
    // `commitGeometryEdit` patches a still-pending create with the update body,
    // so any field they disagree on would silently corrupt the queued create.
    const ids = { entityId: "e-1", annotationId: "k-1" };
    const createBody = bodyOf(buildKeypointsCreate(CTX, GEOMETRY, ids).mutations[1]);
    const updateBody = buildKeypointsUpdate(CTX, ids.annotationId, ids.entityId, GEOMETRY);

    for (const [key, value] of Object.entries(updateBody)) {
      expect(createBody).toHaveProperty(key, value);
    }
  });
});
