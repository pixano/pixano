/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildBBoxCreate,
  buildBBoxUpdate,
  mutationPriority,
  sortMutations,
} from "../buildPayloads";
import type { ResourceMutation } from "../types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

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
    const entityBody = (mutations[0] as Extract<ResourceMutation, { op: "create" }>).body;
    const bboxBody = (mutations[1] as Extract<ResourceMutation, { op: "create" }>).body;

    expect(entityBody.id).toBe(entityId);
    expect(bboxBody.entity_id).toBe(entityId);
  });

  it("encodes coords as normalized xywh with the expected flags", () => {
    const coords: [number, number, number, number] = [0.1, 0.2, 0.3, 0.4];
    const { mutations } = buildBBoxCreate(CTX, coords);
    const bboxBody = (mutations[1] as Extract<ResourceMutation, { op: "create" }>).body;

    expect(bboxBody.coords).toEqual([0.1, 0.2, 0.3, 0.4]);
    expect(bboxBody.format).toBe("xywh");
    expect(bboxBody.is_normalized).toBe(true);
    expect(bboxBody.confidence).toBe(1);
  });

  it("forwards record_id and view_id from the build context", () => {
    const { mutations } = buildBBoxCreate(CTX, [0, 0, 0.5, 0.5]);
    const entityBody = (mutations[0] as Extract<ResourceMutation, { op: "create" }>).body;
    const bboxBody = (mutations[1] as Extract<ResourceMutation, { op: "create" }>).body;

    expect(entityBody.record_id).toBe("rec-1");
    expect(bboxBody.record_id).toBe("rec-1");
    expect(bboxBody.view_id).toBe("view-1");
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

  it("reuses caller-provided entityId and bboxId when given", () => {
    const { entityId, bboxId, mutations } = buildBBoxCreate(CTX, [0, 0, 1, 1], {
      entityId: "my-entity",
      bboxId: "my-bbox",
    });

    expect(entityId).toBe("my-entity");
    expect(bboxId).toBe("my-bbox");
    const entityBody = (mutations[0] as Extract<ResourceMutation, { op: "create" }>).body;
    const bboxBody = (mutations[1] as Extract<ResourceMutation, { op: "create" }>).body;
    expect(entityBody.id).toBe("my-entity");
    expect(bboxBody.id).toBe("my-bbox");
    expect(bboxBody.entity_id).toBe("my-entity");
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
});

describe("mutationPriority / sortMutations", () => {
  it("creates entities before bboxes", () => {
    expect(mutationPriority({ op: "create", resource: "entities", body: {} })).toBeLessThan(
      mutationPriority({ op: "create", resource: "bboxes", body: {} }),
    );
  });

  it("runs deletes after creates", () => {
    const createPriority = mutationPriority({ op: "create", resource: "bboxes", body: {} });
    const deleteBBoxPriority = mutationPriority({ op: "delete", resource: "bboxes", id: "x" });
    expect(deleteBBoxPriority).toBeGreaterThan(createPriority);
  });

  it("deletes entities last so dependent bboxes are removed first", () => {
    const deleteBBox = mutationPriority({ op: "delete", resource: "bboxes", id: "x" });
    const deleteEntity = mutationPriority({ op: "delete", resource: "entities", id: "x" });
    expect(deleteEntity).toBeGreaterThan(deleteBBox);
  });

  it("sortMutations preserves relative order within the same priority", () => {
    const input: ResourceMutation[] = [
      { op: "create", resource: "bboxes", body: { id: "b1" } },
      { op: "create", resource: "entities", body: { id: "e1" } },
      { op: "create", resource: "bboxes", body: { id: "b2" } },
      { op: "create", resource: "entities", body: { id: "e2" } },
    ];

    const sorted = sortMutations(input);

    expect(sorted.map((m) => (m.op === "create" ? m.body.id : m.id))).toEqual([
      "e1",
      "e2",
      "b1",
      "b2",
    ]);
  });

  it("sortMutations produces a full create-then-delete ordering", () => {
    const input: ResourceMutation[] = [
      { op: "delete", resource: "entities", id: "e-old" },
      { op: "create", resource: "bboxes", body: { id: "b-new" } },
      { op: "delete", resource: "bboxes", id: "b-old" },
      { op: "create", resource: "entities", body: { id: "e-new" } },
    ];

    const sorted = sortMutations(input);
    const order = sorted.map((m) => {
      if (m.op === "create") return `create:${m.resource}`;
      return `delete:${m.resource}`;
    });

    expect(order).toEqual([
      "create:entities",
      "create:bboxes",
      "delete:bboxes",
      "delete:entities",
    ]);
  });
});
