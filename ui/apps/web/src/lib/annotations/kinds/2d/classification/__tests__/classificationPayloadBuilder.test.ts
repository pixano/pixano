/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildClassificationBody,
  buildClassificationCreate,
} from "../classificationPayloadBuilder";
import type { ClassificationGeometry } from "../classificationTypes";
import type { ResourceMutation } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

const GEOMETRY: ClassificationGeometry = {
  labels: ["beach", "sunset"],
  confidences: [1, 0.8],
};

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildClassificationCreate", () => {
  it("returns two mutations in (entity, classification) order", () => {
    const { mutations } = buildClassificationCreate(CTX, GEOMETRY);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("classifications");
  });

  it("omits the per-frame linkage columns this schema does not have", () => {
    // `Classification` extends `EntityAnnotation`, not `PerFrameAnnotation`, so
    // it has no frame_id / frame_index / tracklet_id /
    // entity_dynamic_state_id columns — sending them would be rejected.
    const body = bodyOf(buildClassificationCreate(CTX, GEOMETRY).mutations[1]);

    expect(body).not.toHaveProperty("frame_id");
    expect(body).not.toHaveProperty("frame_index");
    expect(body).not.toHaveProperty("tracklet_id");
    expect(body).not.toHaveProperty("entity_dynamic_state_id");
  });

  it("still carries the entity-annotation columns", () => {
    const body = bodyOf(buildClassificationCreate(CTX, GEOMETRY).mutations[1]);

    expect(body.record_id).toBe("rec-1");
    expect(body.view_id).toBe("view-1");
    expect(body.source_type).toBeDefined();
  });

  it("keeps one confidence per label, as the backend requires", () => {
    const body = bodyOf(buildClassificationCreate(CTX, GEOMETRY).mutations[1]);

    expect(body.labels).toEqual(["beach", "sunset"]);
    expect(body.confidences).toEqual([1, 0.8]);
    expect((body.confidences as number[]).length).toBe((body.labels as string[]).length);
  });

  it("copies the arrays rather than aliasing the caller's", () => {
    const geometry: ClassificationGeometry = { ...GEOMETRY, labels: [...GEOMETRY.labels] };
    const body = bodyOf(buildClassificationCreate(CTX, geometry).mutations[1]);

    expect(body.labels).not.toBe(geometry.labels);
    expect(body.confidences).not.toBe(geometry.confidences);
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildClassificationCreate(CTX, GEOMETRY, {
      entityId: "existing-1",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-1");
  });
});

describe("buildClassificationBody", () => {
  it("is byte-for-byte the create body, so D9 holds by construction", () => {
    // With no create-only columns there is nothing for create and update to
    // disagree about — unlike the per-frame kinds, where the linkage is extra.
    const ids = { entityId: "e-1", annotationId: "c-1" };
    const createBody = bodyOf(buildClassificationCreate(CTX, GEOMETRY, ids).mutations[1]);
    const updateBody = buildClassificationBody(CTX, ids.annotationId, ids.entityId, GEOMETRY);

    expect(createBody).toEqual(updateBody);
  });
});
