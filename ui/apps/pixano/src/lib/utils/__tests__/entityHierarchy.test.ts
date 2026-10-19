/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildTopEntityIdByEntityId, type HierarchyEntity } from "../entityHierarchy";

const entity = (id: string, parent_id: unknown = ""): HierarchyEntity => ({
  id,
  data: { parent_id },
});

describe("buildTopEntityIdByEntityId", () => {
  it("maps a top-level entity to itself and every descendant to its top", () => {
    const top = buildTopEntityIdByEntityId([
      entity("car"),
      entity("wheel", "car"),
      entity("bolt", "wheel"),
    ]);

    expect(top.get("car")).toBe("car");
    expect(top.get("wheel")).toBe("car");
    expect(top.get("bolt")).toBe("car");
  });

  it("does not depend on the order of the entities", () => {
    const top = buildTopEntityIdByEntityId([
      entity("bolt", "wheel"),
      entity("wheel", "car"),
      entity("car"),
    ]);

    expect(top.get("bolt")).toBe("car");
  });

  it("maps an entity whose parent is missing to itself", () => {
    const top = buildTopEntityIdByEntityId([entity("orphan", "gone")]);

    expect(top.get("orphan")).toBe("orphan");
  });

  it("treats a non-string parent as no parent", () => {
    const top = buildTopEntityIdByEntityId([entity("a", null), entity("b", 3)]);

    expect(top.get("a")).toBe("a");
    expect(top.get("b")).toBe("b");
  });

  it("terminates on a cycle", () => {
    const top = buildTopEntityIdByEntityId([entity("a", "b"), entity("b", "a")]);

    expect(top.size).toBe(2);
    expect(["a", "b"]).toContain(top.get("a"));
    expect(["a", "b"]).toContain(top.get("b"));
  });
});
