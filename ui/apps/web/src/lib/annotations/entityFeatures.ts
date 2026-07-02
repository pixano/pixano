/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PendingEntityChoice } from "./types.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { FieldInfo } from "$lib/types/dataset.js";

/**
 * Generate and validate the per-field inputs of the "create entity" form from
 * the dataset's entity table schema. This is the apps/web port of pixano's
 * `getValidationSchemaAndFormInputs` (`apps/pixano/src/lib/utils/featureMapping.ts`)
 * and `getDefaultDisplayFeat`, adapted to the workspace's `entitySchemaFields`.
 */

/** Editable scalar field types we render an input for. */
export type EntityFeatureType = "str" | "int" | "float" | "bool" | "list";

export interface EntityFeatureInput {
  name: string;
  label: string;
  type: EntityFeatureType;
  /** Allowed values for `list` fields (none known from the schema yet). */
  options?: string[];
}

/**
 * Entity columns that are structural/linkage rather than user-facing features.
 * The apps/web analogue of pixano's `Entity.nonFeaturesFields()`.
 */
export const ENTITY_SYSTEM_FIELDS = new Set<string>([
  "id",
  "record_id",
  "parent_id",
  "item_id",
  "logical_name",
  "created_at",
  "updated_at",
]);

const SUPPORTED_FEATURE_TYPES = new Set<EntityFeatureType>(["str", "int", "float", "bool", "list"]);

/** Priority of fields treated as the entity's primary display label. */
const LABEL_FIELD_PRIORITY = ["category", "label", "name", "class"] as const;

const FALLBACK_LABEL_FIELD = "name";

/**
 * Build the ordered list of feature inputs for a new entity from its schema
 * fields, skipping system/linkage columns and unsupported types.
 */
export function buildEntityFeatureInputs(
  fields: Record<string, FieldInfo> | null | undefined,
): EntityFeatureInput[] {
  if (!fields) return [];
  const inputs: EntityFeatureInput[] = [];
  for (const [name, info] of Object.entries(fields)) {
    if (ENTITY_SYSTEM_FIELDS.has(name)) continue;
    if (info.collection) continue;
    const type = info.type as EntityFeatureType;
    if (!SUPPORTED_FEATURE_TYPES.has(type)) continue;
    inputs.push({ name, label: name, type, ...(type === "list" ? { options: [] } : {}) });
  }
  return inputs;
}

/**
 * Pick the field that holds an entity's human-readable label. Mirrors the read
 * side (`pickEntityLabel` / `EntitiesPanel.resolveCategory`): a known label
 * field if present as a string, else the first string field, else a fallback.
 */
export function resolveEntityLabelField(
  fields: Record<string, FieldInfo> | null | undefined,
): string {
  if (!fields) return FALLBACK_LABEL_FIELD;
  const isWritableString = (name: string): boolean =>
    !ENTITY_SYSTEM_FIELDS.has(name) && fields[name]?.type === "str" && !fields[name]?.collection;

  for (const candidate of LABEL_FIELD_PRIORITY) {
    if (isWritableString(candidate)) return candidate;
  }
  for (const name of Object.keys(fields)) {
    if (isWritableString(name)) return name;
  }
  return FALLBACK_LABEL_FIELD;
}

/**
 * Distinct non-empty string values already used for `fieldName` across the
 * record's entities. Powers free-text autocomplete suggestions — the apps/web
 * substitute for pixano's `itemMetas.featuresList`.
 */
export function suggestionsForField(entities: EntityRow[], fieldName: string): string[] {
  const seen = new Set<string>();
  for (const entity of entities) {
    const value = entity[fieldName];
    if (typeof value === "string" && value.trim().length > 0) seen.add(value);
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b));
}

/** Default value for a freshly added feature input, by type. */
export function defaultFieldValue(type: EntityFeatureType): string | number | boolean {
  switch (type) {
    case "bool":
      return false;
    case "int":
    case "float":
      return 0;
    case "str":
    case "list":
      return "";
  }
}

/** Coerce a raw form value into the type expected by the backend field. */
export function coerceFieldValue(type: EntityFeatureType, raw: unknown): string | number | boolean {
  switch (type) {
    case "bool":
      return Boolean(raw);
    case "int": {
      const n = Math.trunc(Number(raw));
      return Number.isFinite(n) ? n : 0;
    }
    case "float": {
      const n = Number(raw);
      return Number.isFinite(n) ? n : 0;
    }
    case "str":
    case "list":
      if (typeof raw === "string") return raw;
      if (typeof raw === "number" || typeof raw === "boolean") return String(raw);
      return "";
  }
}

/**
 * Light validity check for the entity form. Linking to an existing entity is
 * always valid; a new entity must at least have a non-empty primary label so it
 * is not anonymous. (The schema carries no `required` info — pixano has the same
 * limitation, see its `required: false` TODO.)
 */
export function isEntityFormValid(choice: PendingEntityChoice, labelField: string): boolean {
  if (choice.mode === "existing") return choice.entityId.length > 0;
  const label = choice.entityFields[labelField];
  return typeof label === "string" && label.trim().length > 0;
}
