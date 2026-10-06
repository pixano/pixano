/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildBBoxCreate, buildBBoxUpdate } from "../bboxPayloadBuilder";
import type { ResourceMutation } from "$lib/annotations/types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildBBoxCreate", () => {
  it("returns two mutations in (entity, bbox) order", () => {
    const { mutations } = buildBBoxCreate(CTX, [0.1, 0.2, 0.3, 0.4]);

    expect(mutations).toHaveLength(2);
    expect(mutations[0].resource).toBe("entities");
    expect(mutations[1].resource).toBe("bboxes");
    expect(mutations[0].op).toBe("create");
    expect(mutations[1].op).toBe("create");
  });

  it("sets matching entity_id between entity and bbox", () => {
    const { entityId, mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1]);

    expect(bodyOf(mutations[0]).id).toBe(entityId);
    expect(bodyOf(mutations[1]).entity_id).toBe(entityId);
  });

  it("encodes coords as normalized xywh with the expected flags", () => {
    const coords: [number, number, number, number] = [0.1, 0.2, 0.3, 0.4];
    const { mutations } = buildBBoxCreate(CTX, coords);
    const bboxBody = bodyOf(mutations[1]);

    expect(bboxBody.coords).toEqual([0.1, 0.2, 0.3, 0.4]);
    expect(bboxBody.format).toBe("xywh");
    expect(bboxBody.is_normalized).toBe(true);
    expect(bboxBody.confidence).toBe(1);
  });

  it("carries the single-frame linkage columns", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1]);
    const bboxBody = bodyOf(mutations[1]);

    // Single-image workspaces reuse the view row id as the frame id.
    expect(bboxBody.frame_id).toBe("view-1");
    expect(bboxBody.frame_index).toBe(-1);
    expect(bboxBody.tracklet_id).toBe("");
    expect(bboxBody.entity_dynamic_state_id).toBe("");
  });

  it("forwards record_id and view_id from the build context", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 0.5, 0.5]);

    expect(bodyOf(mutations[0]).record_id).toBe("rec-1");
    expect(bodyOf(mutations[1]).record_id).toBe("rec-1");
    expect(bodyOf(mutations[1]).view_id).toBe("view-1");
  });

  it("propagates widgetId and localAnnotationId onto every generated mutation", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 0.5, 0.5], {
      widgetId: "widget-1",
      localAnnotationId: "local-1",
    });

    for (const m of mutations) {
      expect(m.widgetId).toBe("widget-1");
      expect(m.localAnnotationId).toBe("local-1");
    }
  });

  it("reuses caller-provided entityId and annotationId when given", () => {
    const { entityId, annotationId, mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1], {
      entityId: "my-entity",
      annotationId: "my-bbox",
    });

    expect(entityId).toBe("my-entity");
    expect(annotationId).toBe("my-bbox");
    expect(bodyOf(mutations[0]).id).toBe("my-entity");
    expect(bodyOf(mutations[1]).id).toBe("my-bbox");
    expect(bodyOf(mutations[1]).entity_id).toBe("my-entity");
  });

  it("merges entityFields onto the new entity body", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1], {
      entityFields: { category: "car", is_difficult: false },
    });
    const entityBody = bodyOf(mutations[0]);

    expect(entityBody.category).toBe("car");
    expect(entityBody.is_difficult).toBe(false);
    // System fields are still present.
    expect(entityBody.parent_id).toBe("");
  });

  it("omits the entity create when linking to an existing entity", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1], {
      entityId: "existing-1",
      linkExisting: true,
    });

    expect(mutations).toHaveLength(1);
    expect(mutations[0].resource).toBe("bboxes");
    expect(bodyOf(mutations[0]).entity_id).toBe("existing-1");
  });
});

describe("buildBBoxUpdate", () => {
  it("returns an update body with the new normalized coords", () => {
    const body = buildBBoxUpdate(CTX, "bbox-1", "entity-1", [0.5, 0.5, 0.25, 0.25]);

    expect(body.id).toBe("bbox-1");
    expect(body.entity_id).toBe("entity-1");
    expect(body.coords).toEqual([0.5, 0.5, 0.25, 0.25]);
    expect(body.format).toBe("xywh");
    expect(body.is_normalized).toBe(true);
  });

  it("is a subset of the create body with identical values (D9)", () => {
    // `commitGeometryEdit` patches a still-pending create with the update body,
    // so any field they disagree on would silently corrupt the queued create.
    const coords: [number, number, number, number] = [0.5, 0.5, 0.25, 0.25];
    const ids = { entityId: "e-1", annotationId: "b-1" };
    const createBody = bodyOf(buildBBoxCreate(CTX, coords, ids).mutations[1]);
    const updateBody = buildBBoxUpdate(CTX, ids.annotationId, ids.entityId, coords);

    for (const [key, value] of Object.entries(updateBody)) {
      expect(createBody).toHaveProperty(key, value);
    }
  });
});
