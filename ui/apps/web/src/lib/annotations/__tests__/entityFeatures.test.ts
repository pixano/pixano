/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildEntityFeatureInputs,
  coerceFieldValue,
  isEntityFormValid,
  resolveEntityLabelField,
  suggestionsForField,
} from "../entityFeatures";
import type { EntityRow } from "$lib/api/annotations";
import type { FieldInfo } from "$lib/types/dataset";

function field(type: string, collection = false): FieldInfo {
  return { type, collection };
}

const CATEGORY_ENTITY: Record<string, FieldInfo> = {
  id: field("str"),
  record_id: field("str"),
  parent_id: field("str"),
  category: field("str"),
  score: field("float"),
  is_difficult: field("bool"),
  tags: field("str", true),
};

describe("buildEntityFeatureInputs", () => {
  it("keeps editable feature fields and drops system / collection fields", () => {
    const inputs = buildEntityFeatureInputs(CATEGORY_ENTITY);
    const names = inputs.map((i) => i.name);

    expect(names).toContain("category");
    expect(names).toContain("score");
    expect(names).toContain("is_difficult");
    expect(names).not.toContain("id");
    expect(names).not.toContain("record_id");
    expect(names).not.toContain("parent_id");
    expect(names).not.toContain("tags"); // collection
  });

  it("maps field types onto input types", () => {
    const inputs = buildEntityFeatureInputs(CATEGORY_ENTITY);
    expect(inputs.find((i) => i.name === "category")?.type).toBe("str");
    expect(inputs.find((i) => i.name === "score")?.type).toBe("float");
    expect(inputs.find((i) => i.name === "is_difficult")?.type).toBe("bool");
  });

  it("returns an empty list when no schema is available", () => {
    expect(buildEntityFeatureInputs(null)).toEqual([]);
  });
});

describe("resolveEntityLabelField", () => {
  it("prefers a known label field when present", () => {
    expect(resolveEntityLabelField(CATEGORY_ENTITY)).toBe("category");
  });

  it("falls back to the first writable string field", () => {
    expect(
      resolveEntityLabelField({
        id: field("str"),
        title: field("str"),
        score: field("float"),
      }),
    ).toBe("title");
  });

  it("falls back to a default when there is no string field", () => {
    expect(resolveEntityLabelField({ id: field("str"), score: field("float") })).toBe("name");
    expect(resolveEntityLabelField(null)).toBe("name");
  });
});

describe("suggestionsForField", () => {
  it("returns distinct non-empty sorted values", () => {
    const entities = [
      { id: "1", record_id: "r", category: "car" },
      { id: "2", record_id: "r", category: "bike" },
      { id: "3", record_id: "r", category: "car" },
      { id: "4", record_id: "r", category: "" },
    ] as unknown as EntityRow[];

    expect(suggestionsForField(entities, "category")).toEqual(["bike", "car"]);
  });
});

describe("coerceFieldValue", () => {
  it("coerces values to their field type", () => {
    expect(coerceFieldValue("int", "3.7")).toBe(3);
    expect(coerceFieldValue("float", "2.5")).toBe(2.5);
    expect(coerceFieldValue("bool", true)).toBe(true);
    expect(coerceFieldValue("str", 42)).toBe("42");
    expect(coerceFieldValue("int", "")).toBe(0);
  });
});

describe("isEntityFormValid", () => {
  it("accepts an existing entity selection", () => {
    expect(isEntityFormValid({ mode: "existing", entityId: "e1" }, "category")).toBe(true);
    expect(isEntityFormValid({ mode: "existing", entityId: "" }, "category")).toBe(false);
  });

  it("requires a non-empty primary label for a new entity", () => {
    expect(isEntityFormValid({ mode: "new", entityFields: { category: "car" } }, "category")).toBe(
      true,
    );
    expect(isEntityFormValid({ mode: "new", entityFields: { category: "  " } }, "category")).toBe(
      false,
    );
    expect(isEntityFormValid({ mode: "new", entityFields: {} }, "category")).toBe(false);
  });
});
