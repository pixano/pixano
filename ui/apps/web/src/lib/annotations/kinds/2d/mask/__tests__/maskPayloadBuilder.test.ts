/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildMaskCreate, buildMaskUpdate } from "../maskPayloadBuilder";
import type { MaskGeometry } from "../maskTypes";
import type { ResourceMutation } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

const GEOMETRY: MaskGeometry = { size: [4, 6], counts: "a2b1" };

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildMaskCreate", () => {
  it("returns two mutations in (entity, mask) order", () => {
    const { mutations } = buildMaskCreate(CTX, GEOMETRY);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("masks");
  });

  it("sends the RLE through untouched", () => {
    const { mutations } = buildMaskCreate(CTX, GEOMETRY);
    const body = bodyOf(mutations[1]);

    expect(body.counts).toBe("a2b1");
    expect(body.size).toEqual([4, 6]);
  });

  it("omits confidence, which CompressedRLE has no column for", () => {
    // BBox carries `confidence`; the mask schema does not, and the backend
    // rejects unknown fields.
    const { mutations } = buildMaskCreate(CTX, GEOMETRY);
    expect(bodyOf(mutations[1])).not.toHaveProperty("confidence");
  });

  it("carries the single-frame linkage columns", () => {
    const { mutations } = buildMaskCreate(CTX, GEOMETRY);
    const body = bodyOf(mutations[1]);

    expect(body.frame_id).toBe("view-1");
    expect(body.frame_index).toBe(-1);
    expect(body.tracklet_id).toBe("");
    expect(body.entity_dynamic_state_id).toBe("");
  });

  it("sets matching entity_id between entity and mask", () => {
    const { entityId, mutations } = buildMaskCreate(CTX, GEOMETRY);

    expect(bodyOf(mutations[0]).id).toBe(entityId);
    expect(bodyOf(mutations[1]).entity_id).toBe(entityId);
  });

  it("merges entityFields onto the new entity body", () => {
    const { mutations } = buildMaskCreate(CTX, GEOMETRY, {
      entityFields: { category: "road" },
    });
    expect(bodyOf(mutations[0]).category).toBe("road");
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildMaskCreate(CTX, GEOMETRY, {
      entityId: "existing-1",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(mutations[0].resource).toBe("masks");
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-1");
  });

  it("copies size rather than aliasing the caller's array", () => {
    // The collection keeps the geometry object; a body holding the same array
    // reference would mutate the queued payload on the next edit.
    const geometry: MaskGeometry = { size: [4, 6], counts: "a2b1" };
    const { mutations } = buildMaskCreate(CTX, geometry);
    expect(bodyOf(mutations[1]).size).not.toBe(geometry.size);
  });
});

describe("buildMaskUpdate", () => {
  it("returns an update body with the new encoding", () => {
    const body = buildMaskUpdate(CTX, "m-1", "e-1", { size: [2, 3], counts: "xyz" });

    expect(body.id).toBe("m-1");
    expect(body.entity_id).toBe("e-1");
    expect(body.size).toEqual([2, 3]);
    expect(body.counts).toBe("xyz");
  });

  it("is a subset of the create body with identical values (D9)", () => {
    // `commitGeometryEdit` patches a still-pending create with the update body,
    // so any field they disagree on would silently corrupt the queued create.
    const ids = { entityId: "e-1", annotationId: "m-1" };
    const createBody = bodyOf(buildMaskCreate(CTX, GEOMETRY, ids).mutations[1]);
    const updateBody = buildMaskUpdate(CTX, ids.annotationId, ids.entityId, GEOMETRY);

    for (const [key, value] of Object.entries(updateBody)) {
      expect(createBody).toHaveProperty(key, value);
    }
  });
});
