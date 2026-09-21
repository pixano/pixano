/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildCreateMutations,
  buildEntityCreateMutation,
  mutationPriority,
  singleFrameLinkage,
  sortMutations,
} from "../buildPayloads";
import type { ResourceMutation } from "../types";

const CTX = {
  datasetId: "ds-1",
  recordId: "rec-1",
  viewId: "view-1",
};

/** Narrow a create mutation to its body without repeating the cast everywhere. */
function bodyOf(m: ResourceMutation): Record<string, unknown> {
  return (m as Extract<ResourceMutation, { op: "create" }>).body;
}

describe("buildEntityCreateMutation", () => {
  it("builds the system fields and merges the caller's entity fields", () => {
    const m = buildEntityCreateMutation(CTX, "e-1", { category: "car" }, "w-1", "local-1");

    expect(m.resource).toBe("entities");
    expect(m.op).toBe("create");
    expect(bodyOf(m)).toEqual({
      id: "e-1",
      record_id: "rec-1",
      parent_id: "",
      category: "car",
    });
    expect(m.widgetId).toBe("w-1");
    expect(m.localAnnotationId).toBe("local-1");
  });
});

describe("singleFrameLinkage", () => {
  it("reuses the view row id as the frame id (single-image scope, D2)", () => {
    expect(singleFrameLinkage(CTX)).toEqual({
      frame_id: "view-1",
      frame_index: -1,
      tracklet_id: "",
      entity_dynamic_state_id: "",
    });
  });
});

describe("buildCreateMutations", () => {
  const IDS = { entityId: "e-1", annotationId: "a-1" };

  it("emits the entity create before the annotation create", () => {
    const mutations = buildCreateMutations(CTX, "masks", IDS, { id: "a-1" }, {});

    expect(mutations.map((m) => m.resource)).toEqual(["entities", "masks"]);
  });

  it("omits the entity create when linking an existing entity", () => {
    const mutations = buildCreateMutations(
      CTX,
      "masks",
      IDS,
      { id: "a-1" },
      {
        linkExisting: true,
      },
    );

    expect(mutations).toHaveLength(1);
    expect(mutations[0].resource).toBe("masks");
  });

  it("propagates widgetId and localAnnotationId onto every mutation", () => {
    const mutations = buildCreateMutations(
      CTX,
      "masks",
      IDS,
      { id: "a-1" },
      {
        widgetId: "w-1",
        localAnnotationId: "local-1",
      },
    );

    for (const m of mutations) {
      expect(m.widgetId).toBe("w-1");
      expect(m.localAnnotationId).toBe("local-1");
    }
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

    expect(order).toEqual(["create:entities", "create:bboxes", "delete:bboxes", "delete:entities"]);
  });
});
