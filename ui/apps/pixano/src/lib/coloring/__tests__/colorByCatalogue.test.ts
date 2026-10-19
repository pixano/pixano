/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  buildColorByCatalogue,
  EMPTY_COLOR_BY_CATALOGUE,
  ENTITY_COLOR_MODE,
} from "../colorByCatalogue";
import { BaseSchema, type FieldInfo } from "$lib/types/dataset";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

type Tables = Record<string, { baseSchema: BaseSchema; fields?: Record<string, FieldInfo> }>;

const field = (type: string, collection = false): FieldInfo => ({ type, collection });

function manifest(
  entities: Tables,
  annotations: Tables = {},
): Pick<WorkspaceManifest, "tablesByName" | "tablesByGroup"> {
  const tablesByName: WorkspaceManifest["tablesByName"] = {};
  for (const [name, table] of Object.entries(entities)) {
    tablesByName[name] = {
      name,
      group: "entities",
      baseSchema: table.baseSchema,
      fields: table.fields ?? {},
    };
  }
  for (const [name, table] of Object.entries(annotations)) {
    tablesByName[name] = {
      name,
      group: "annotations",
      baseSchema: table.baseSchema,
      fields: table.fields ?? {},
    };
  }
  return {
    tablesByName,
    tablesByGroup: {
      entities: Object.keys(entities),
      annotations: Object.keys(annotations),
      item: [],
      views: [],
      embeddings: [],
    },
  };
}

const ids = (catalogue: ReturnType<typeof buildColorByCatalogue>) =>
  catalogue.attributes.map((attribute) => attribute.id);

describe("buildColorByCatalogue", () => {
  it("offers nothing without a manifest or without attributes", () => {
    expect(buildColorByCatalogue(null)).toBe(EMPTY_COLOR_BY_CATALOGUE);
    expect(buildColorByCatalogue(undefined)).toBe(EMPTY_COLOR_BY_CATALOGUE);
    expect(buildColorByCatalogue(manifest({ entities: { baseSchema: BaseSchema.Entity } }))).toBe(
      EMPTY_COLOR_BY_CATALOGUE,
    );
  });

  it("offers scalar entity fields, the label field first", () => {
    const catalogue = buildColorByCatalogue(
      manifest({
        entities: {
          baseSchema: BaseSchema.Entity,
          fields: {
            is_difficult: field("bool"),
            score: field("float"),
            category: field("str"),
            count: field("int"),
            tags: field("str", true),
            created: field("datetime"),
            embedding: field("NDArrayFloat"),
            legacy: field("list"),
          },
        },
      }),
    );

    expect(ids(catalogue)).toEqual([
      "entities.category",
      "entities.is_difficult",
      "entities.score",
      "entities.count",
    ]);
    expect(catalogue.attributes.every((attribute) => attribute.scope === "entity")).toBe(true);
  });

  it("never offers links or identifiers, even declared as custom fields", () => {
    const catalogue = buildColorByCatalogue(
      manifest({
        entities: {
          baseSchema: BaseSchema.Entity,
          fields: {
            parent_id: field("str"),
            record_id: field("str"),
            view_id: field("str"),
            frame_id: field("str"),
            source_metadata: field("str"),
            name: field("str"),
          },
        },
      }),
    );

    expect(ids(catalogue)).toEqual(["entities.name"]);
  });

  it("chooses the scale from the field type", () => {
    const catalogue = buildColorByCatalogue(
      manifest({
        entities: {
          baseSchema: BaseSchema.Entity,
          fields: {
            category: field("str"),
            flag: field("bool"),
            count: field("int"),
            score: field("float"),
          },
        },
      }),
    );
    const scaleOf = (id: string) => catalogue.byId.get(id)?.scale;

    expect(scaleOf("entities.category")).toBe("categorical");
    expect(scaleOf("entities.flag")).toBe("categorical");
    expect(scaleOf("entities.count")).toBe("numeric");
    expect(scaleOf("entities.score")).toBe("numeric");
    expect(catalogue.byId.get("entities.flag")?.seeds).toEqual(["false", "true"]);
    expect(catalogue.byId.get("entities.category")?.seeds).toBeUndefined();
  });

  it("offers annotation fields by family, then the box confidence", () => {
    const catalogue = buildColorByCatalogue(
      manifest(
        { entities: { baseSchema: BaseSchema.Entity, fields: { category: field("str") } } },
        {
          tracklets: { baseSchema: BaseSchema.Tracklet, fields: { phase: field("str") } },
          text_spans: { baseSchema: BaseSchema.TextSpan, fields: { role: field("str") } },
          keypoints: { baseSchema: BaseSchema.Keypoints, fields: { pose: field("str") } },
          multi_paths: { baseSchema: BaseSchema.MultiPath, fields: { quality: field("int") } },
          masks: { baseSchema: BaseSchema.Mask, fields: { material: field("str") } },
          bboxes: { baseSchema: BaseSchema.BBox, fields: { annotator: field("str") } },
          messages: { baseSchema: BaseSchema.Message, fields: { mood: field("str") } },
          entity_dynamic_states: {
            baseSchema: BaseSchema.Classification,
            fields: { occluded: field("bool") },
          },
        },
      ),
    );

    expect(ids(catalogue)).toEqual([
      "entities.category",
      "bboxes.annotator",
      "bboxes.confidence",
      "masks.material",
      "multi_paths.quality",
      "keypoints.pose",
      "text_spans.role",
      "tracklets.phase",
    ]);
    const annotator = catalogue.byId.get("bboxes.annotator");
    expect(annotator).toMatchObject({
      scope: "annotation",
      table: "bboxes",
      baseSchema: BaseSchema.BBox,
      field: "annotator",
    });
  });

  it("offers the box confidence once, on a fixed 0-1 range where -1 means no value", () => {
    const catalogue = buildColorByCatalogue(
      manifest(
        { entities: { baseSchema: BaseSchema.Entity } },
        { bboxes: { baseSchema: BaseSchema.BBox, fields: { confidence: field("float") } } },
      ),
    );

    expect(ids(catalogue)).toEqual(["bboxes.confidence"]);
    expect(catalogue.byId.get("bboxes.confidence")).toMatchObject({
      scale: "numeric",
      fixedDomain: [0, 1],
      noValueBelow: 0,
      label: "Confidence",
    });
  });

  it("offers no confidence without a box table", () => {
    const catalogue = buildColorByCatalogue(
      manifest(
        { entities: { baseSchema: BaseSchema.Entity } },
        { masks: { baseSchema: BaseSchema.Mask } },
      ),
    );

    expect(catalogue).toBe(EMPTY_COLOR_BY_CATALOGUE);
  });

  it("ignores entity tables that are not entities, and keeps ids unique", () => {
    const catalogue = buildColorByCatalogue(
      manifest({
        entities: { baseSchema: BaseSchema.Entity, fields: { category: field("str") } },
        conversations: { baseSchema: BaseSchema.Conversation, fields: { topic: field("str") } },
      }),
    );

    expect(ids(catalogue)).toEqual(["entities.category"]);
    expect(new Set(ids(catalogue)).size).toBe(catalogue.attributes.length);
    expect(ids(catalogue)).not.toContain(ENTITY_COLOR_MODE);
  });

  it("humanizes labels", () => {
    const catalogue = buildColorByCatalogue(
      manifest({
        entities: {
          baseSchema: BaseSchema.Entity,
          fields: { is_difficult: field("bool"), category_name: field("str") },
        },
      }),
    );

    expect(catalogue.attributes.map((attribute) => attribute.label)).toEqual([
      "Category name",
      "Is difficult",
    ]);
  });

  it("gives equal schemas the same signature, and a type change a new one", () => {
    const build = (type: string) =>
      buildColorByCatalogue(
        manifest({ entities: { baseSchema: BaseSchema.Entity, fields: { score: field(type) } } }),
      );

    expect(build("float").signature).toBe(build("float").signature);
    expect(build("float").signature).not.toBe(build("str").signature);
  });
});
