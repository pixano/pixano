/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildBBox3DCreate, buildBBox3DUpdate, DEFAULT_3D_ROTATION } from "../bbox3dPayloadBuilder";
import type { ResourceMutation, Rotation3x3 } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

const COORDS: [number, number, number, number, number, number] = [1, 2, 3, 4, 5, 6];

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildBBox3DCreate", () => {
  it("returns (entity, bbox3d) create mutations with a matching entity_id", () => {
    const { entityId, mutations } = buildBBox3DCreate(CTX, COORDS);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("bbox3ds");
    expect(bodyOf(mutations[1]).entity_id).toBe(entityId);
    expect(bodyOf(mutations[1]).format).toBe("xyzwhd");
  });

  it("carries the single-frame linkage columns", () => {
    const { mutations } = buildBBox3DCreate(CTX, COORDS);
    const body = bodyOf(mutations[1]);

    expect(body.frame_id).toBe("view-1");
    expect(body.frame_index).toBe(-1);
    expect(body.tracklet_id).toBe("");
    expect(body.entity_dynamic_state_id).toBe("");
  });

  it("merges entityFields onto the new entity body", () => {
    const { mutations } = buildBBox3DCreate(CTX, COORDS, {
      entityFields: { category: "pedestrian" },
    });
    expect(bodyOf(mutations[0]).category).toBe("pedestrian");
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildBBox3DCreate(CTX, COORDS, {
      entityId: "existing-3d",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(mutations[0].resource).toBe("bbox3ds");
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-3d");
  });
});

describe("buildBBox3DUpdate", () => {
  it("defaults to the identity rotation for an axis-aligned box", () => {
    const body = buildBBox3DUpdate(CTX, "b-1", "e-1", COORDS);
    expect(body.rotation).toEqual(DEFAULT_3D_ROTATION);
  });

  it("keeps a supplied rotation", () => {
    const rotation: Rotation3x3 = [0, -1, 0, 1, 0, 0, 0, 0, 1];
    const body = buildBBox3DUpdate(CTX, "b-1", "e-1", COORDS, rotation);
    expect(body.rotation).toEqual(rotation);
  });

  it("is a subset of the create body with identical values (D9)", () => {
    // `commitGeometryEdit` patches a still-pending create with the update body,
    // so any field they disagree on would silently corrupt the queued create.
    const ids = { entityId: "e-1", annotationId: "b-1" };
    const createBody = bodyOf(buildBBox3DCreate(CTX, COORDS, ids).mutations[1]);
    const updateBody = buildBBox3DUpdate(CTX, ids.annotationId, ids.entityId, COORDS);

    for (const [key, value] of Object.entries(updateBody)) {
      expect(createBody).toHaveProperty(key, value);
    }
  });
});
