/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  MultiPath,
  TextSpan,
  Tracklet,
  type FieldInfo,
} from "$lib/types/dataset";
import { humanizeFieldName } from "$lib/utils/labels";
import { resolveEntityLabelField } from "$lib/utils/workspaceDefaultFeatures";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

/** The "Color by" option that keeps one color per object. */
export const ENTITY_COLOR_MODE = "entity";

export type ColorByScope = "entity" | "annotation";
export type ColorByScale = "categorical" | "numeric";
export type ColorByFieldType = "str" | "int" | "float" | "bool";

/** An attribute annotations can be colored by. */
export interface ColorByAttribute {
  /** `<table>.<field>`: table names have no dot, so it never equals ENTITY_COLOR_MODE. */
  readonly id: string;
  readonly scope: ColorByScope;
  readonly table: string;
  readonly baseSchema: BaseSchema;
  readonly field: string;
  readonly fieldType: ColorByFieldType;
  readonly label: string;
  readonly scale: ColorByScale;
  /** Values that take the first colors, in this order, before any value is seen. */
  readonly seeds?: readonly string[];
  /** A range that does not depend on the data. */
  readonly fixedDomain?: readonly [number, number];
  /** Numbers below this bound mean "no value" (a box confidence of -1 is "not predicted"). */
  readonly noValueBelow?: number;
}

export interface ColorByCatalogue {
  readonly attributes: readonly ColorByAttribute[];
  readonly byId: ReadonlyMap<string, ColorByAttribute>;
  /** Equal for catalogues that offer the same attributes with the same types. */
  readonly signature: string;
}

export const EMPTY_COLOR_BY_CATALOGUE: ColorByCatalogue = Object.freeze({
  attributes: Object.freeze([]) as readonly ColorByAttribute[],
  byId: new Map<string, ColorByAttribute>(),
  signature: "",
});

type ColorByManifest = Pick<WorkspaceManifest, "tablesByName" | "tablesByGroup">;

const SCALAR_TYPES = new Set<string>(["str", "int", "float", "bool"]);

// Links, identifiers and metadata a dataset may still carry as custom columns: never a color.
const NEVER_OFFERED = new Set([
  "id",
  "created_at",
  "updated_at",
  "item_id",
  "record_id",
  "parent_id",
  "entity_id",
  "entity_ids",
  "view_id",
  "view_name",
  "frame_id",
  "frame_index",
  "tracklet_id",
  "entity_dynamic_state_id",
  "conversation_id",
  "source_id",
  "source_metadata",
  "inference_metadata",
  "start_timestep",
  "end_timestep",
]);

// Families whose rows are drawn, in the order the selector lists them.
const ANNOTATION_FAMILIES: ReadonlyArray<{
  baseSchema: BaseSchema;
  nonFeatures: ReadonlySet<string>;
}> = [
  { baseSchema: BaseSchema.BBox, nonFeatures: new Set(BBox.nonFeaturesFields()) },
  { baseSchema: BaseSchema.Mask, nonFeatures: new Set(Mask.nonFeaturesFields()) },
  { baseSchema: BaseSchema.MultiPath, nonFeatures: new Set(MultiPath.nonFeaturesFields()) },
  { baseSchema: BaseSchema.Keypoints, nonFeatures: new Set(Keypoints.nonFeaturesFields()) },
  { baseSchema: BaseSchema.TextSpan, nonFeatures: new Set(TextSpan.nonFeaturesFields()) },
  { baseSchema: BaseSchema.Tracklet, nonFeatures: new Set(Tracklet.nonFeaturesFields()) },
];

const ENTITY_NON_FEATURES = new Set(Entity.nonFeaturesFields());

function isColorableField(
  field: string,
  info: FieldInfo | undefined,
  nonFeatures: ReadonlySet<string>,
): boolean {
  return (
    !!info &&
    !info.collection &&
    SCALAR_TYPES.has(info.type) &&
    !nonFeatures.has(field) &&
    !NEVER_OFFERED.has(field)
  );
}

function makeAttribute(
  scope: ColorByScope,
  table: string,
  baseSchema: BaseSchema,
  field: string,
  fieldType: ColorByFieldType,
  extra: Pick<ColorByAttribute, "fixedDomain" | "noValueBelow"> = {},
): ColorByAttribute {
  const scale: ColorByScale =
    fieldType === "int" || fieldType === "float" ? "numeric" : "categorical";
  return {
    id: `${table}.${field}`,
    scope,
    table,
    baseSchema,
    field,
    fieldType,
    label: humanizeFieldName(field),
    scale,
    ...(fieldType === "bool" ? { seeds: ["false", "true"] } : {}),
    ...extra,
  };
}

function entityAttributes(manifest: ColorByManifest): ColorByAttribute[] {
  const attributes: ColorByAttribute[] = [];
  for (const table of manifest.tablesByGroup.entities ?? []) {
    const tableManifest = manifest.tablesByName[table];
    if (tableManifest?.baseSchema !== BaseSchema.Entity) continue;
    const fields = Object.keys(tableManifest.fields ?? {}).filter((field) =>
      isColorableField(field, tableManifest.fields[field], ENTITY_NON_FEATURES),
    );
    const labelField = resolveEntityLabelField(fields);
    const ordered = labelField ? [labelField, ...fields.filter((f) => f !== labelField)] : fields;
    for (const field of ordered) {
      const fieldType = tableManifest.fields[field].type as ColorByFieldType;
      attributes.push(makeAttribute("entity", table, BaseSchema.Entity, field, fieldType));
    }
  }
  return attributes;
}

function annotationAttributes(manifest: ColorByManifest): ColorByAttribute[] {
  const attributes: ColorByAttribute[] = [];
  const tables = manifest.tablesByGroup.annotations ?? [];
  for (const family of ANNOTATION_FAMILIES) {
    for (const table of tables) {
      const tableManifest = manifest.tablesByName[table];
      if (tableManifest?.baseSchema !== family.baseSchema) continue;
      const fields = tableManifest.fields ?? {};
      for (const field of Object.keys(fields)) {
        if (!isColorableField(field, fields[field], family.nonFeatures)) continue;
        const fieldType = fields[field].type as ColorByFieldType;
        attributes.push(makeAttribute("annotation", table, family.baseSchema, field, fieldType));
      }
      // A base field the schema does not list: a model's score, -1 when nothing predicted it.
      if (family.baseSchema === BaseSchema.BBox) {
        attributes.push(
          makeAttribute("annotation", table, family.baseSchema, "confidence", "float", {
            fixedDomain: [0, 1],
            noValueBelow: 0,
          }),
        );
      }
    }
  }
  return attributes;
}

/**
 * The attributes a dataset's annotations can be colored by, read from its schema.
 *
 * The list depends on the schema only, never on the rows of a record, so a choice made on one
 * record stays available on the next.
 */
export function buildColorByCatalogue(
  manifest: ColorByManifest | null | undefined,
): ColorByCatalogue {
  if (!manifest?.tablesByName || !manifest.tablesByGroup) return EMPTY_COLOR_BY_CATALOGUE;
  const attributes = [...entityAttributes(manifest), ...annotationAttributes(manifest)];
  if (attributes.length === 0) return EMPTY_COLOR_BY_CATALOGUE;
  return {
    attributes,
    byId: new Map(attributes.map((attribute) => [attribute.id, attribute])),
    signature: attributes.map((attribute) => `${attribute.id}:${attribute.fieldType}`).join("|"),
  };
}
