/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  createFeature,
  getEntityProperties,
  getValidationSchemaAndFormInputs,
  mapFeatureList,
  mapShapeInputsToFeatures,
} from "../featureMapping";
import { inputsForEntitySelection, validateEntityForm } from "../featureValidationSchemas";
import { serializeSchema } from "$lib/api/resourcePayloads";
import {
  BaseSchema,
  Entity,
  WorkspaceType,
  type FeatureList,
  type FieldInfo,
} from "$lib/types/dataset";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

vi.mock("$lib/stores/workspaceStores.svelte", () => ({ views: { value: {} } }));

function manifest(fields: Record<string, FieldInfo>): WorkspaceManifest {
  return {
    workspaceType: WorkspaceType.VIDEO,
    tablesByName: {
      entities: { name: "entities", group: "entities", baseSchema: BaseSchema.Entity, fields },
      bboxes: {
        name: "bboxes",
        group: "annotations",
        baseSchema: BaseSchema.BBox,
        fields: { quality: { type: "int", collection: false, required: true } },
      },
    },
    tablesByGroup: {
      entities: ["entities"],
      annotations: ["bboxes"],
      item: [],
      views: [],
      embeddings: [],
    },
    baseSchemaToTable: {},
    relations: {},
  };
}

describe("feature option rendering", () => {
  it("sorts displayed options without writing to shared reactive feature data", () => {
    const values = ["zebra", "apple"];
    Object.freeze(values);
    const featureList = Object.freeze({ restricted: false, values });
    expect(mapFeatureList(featureList)).toEqual([
      { value: "apple", label: "apple" },
      { value: "zebra", label: "zebra" },
    ]);
    expect(values).toEqual(["zebra", "apple"]);
  });

  it("handles absent options without adding defaults to the source object", () => {
    const featureList = Object.freeze({}) as FeatureList;
    expect(mapFeatureList(featureList)).toEqual([]);
    expect(featureList).toEqual({});
    expect(mapFeatureList()).toEqual([]);
  });
});

describe("schema attributes in annotation forms", () => {
  it("preserves defaults and required flags while keeping typed arrays distinct from enum strings", () => {
    const schema = manifest({
      category: { type: "str", collection: false, required: true },
      visible: { type: "bool", collection: false, default: true },
      score: { type: "float", collection: false, default: 0.5 },
      caption: { type: "str", collection: false, default: "unknown" },
      tags: { type: "str", collection: true, default: ["robot"] },
      legacy: { type: "list", collection: false },
    });
    const { inputs } = getValidationSchemaAndFormInputs(schema, BaseSchema.BBox);
    expect(inputs.find((input) => input.name === "category")?.required).toBe(true);
    expect(inputs.find((input) => input.name === "tags")).toMatchObject({
      type: "collection",
      itemType: "str",
    });
    expect(inputs.find((input) => input.name === "legacy")?.type).toBe("list");
    const values = getEntityProperties(inputs, {}, {});
    expect(values.entities).toMatchObject({
      visible: true,
      score: 0.5,
      caption: "unknown",
      tags: ["robot"],
    });
    expect(validateEntityForm(inputs, values).success).toBe(false);
    values.entities.category = "gripper";
    values.bboxes.quality = 0;
    expect(validateEntityForm(inputs, values).success).toBe(true);
    (values.entities.tags as string[]).push("tool");
    expect(schema.tablesByName.entities.fields.tags.default).toEqual(["robot"]);
  });

  it("keeps collections typed through creation payloads and later feature editing", () => {
    const schema = manifest({
      tags: { type: "str", collection: true, default: ["red", "two, words"] },
      counts: { type: "int", collection: true, default: [1, 2] },
      scores: { type: "float", collection: true, default: [0.5] },
      flags: { type: "bool", collection: true, default: [true, false] },
    });
    const { inputs } = getValidationSchemaAndFormInputs(schema, BaseSchema.BBox);
    const values = getEntityProperties(inputs, {}, {});
    const features = mapShapeInputsToFeatures(values, inputs);
    const entity = new Entity({
      id: "entity1",
      created_at: "",
      updated_at: "",
      table_info: { name: "entities", group: "entities", base_schema: BaseSchema.Entity },
      data: {
        item_id: "record1",
        parent_id: "",
        ...Object.fromEntries(Object.values(features.entities).map((f) => [f.name, f.value])),
      },
    });
    expect(serializeSchema(entity)).toMatchObject({
      record_id: "record1",
      tags: ["red", "two, words"],
      counts: [1, 2],
      scores: [0.5],
      flags: [true, false],
    });
    expect(createFeature(entity, schema).find((feature) => feature.name === "flags")).toMatchObject(
      { type: "collection", itemType: "bool", value: [true, false] },
    );
    entity.data.flags = [false];
    expect(serializeSchema(entity).flags).toEqual([false]);
    expect(getEntityProperties(inputs, features, {}).entities.tags).toEqual(["red", "two, words"]);
  });

  it("does not let new-entity requirements block relinking to an existing entity", () => {
    const schema = manifest({ category: { type: "str", collection: false, required: true } });
    const { inputs } = getValidationSchemaAndFormInputs(schema, BaseSchema.BBox);
    const values = { bboxes: { quality: 0 } };
    expect(validateEntityForm(inputsForEntitySelection(inputs, "new"), values).success).toBe(false);
    expect(
      validateEntityForm(inputsForEntitySelection(inputs, "existing-entity"), values).success,
    ).toBe(true);
    expect(
      validateEntityForm(inputsForEntitySelection(inputs, "existing-entity"), {}).success,
    ).toBe(false);
  });

  it("copies defaults from reactive proxy arrays without cloning the proxy", () => {
    const tags = new Proxy(["robot"], {});
    const schema = manifest({ tags: { type: "str", collection: true, default: tags } });
    const { inputs } = getValidationSchemaAndFormInputs(schema, BaseSchema.BBox);
    const values = getEntityProperties(inputs, {}, {});
    expect(values.entities.tags).toEqual(["robot"]);
    expect(values.entities.tags).not.toBe(tags);
  });
});
