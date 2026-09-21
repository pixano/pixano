/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BaseSchema } from "$lib/types/dataset";
import { humanizeFieldName } from "$lib/utils/labels";

export interface TableInfo {
  name: string;
  group: string;
  base_schema: BaseSchema;
}

/** A validation error attached to a specific form field. */
export interface FieldError {
  /** Field name (schema field key). */
  name: string;
  /** Owning table name (`sch.name`). */
  sch: string;
  /** Human-readable message. */
  message: string;
}

export interface ListInput {
  name: string;
  label: string;
  type: "list";
  required?: boolean;
  default?: unknown;
  options: Array<{ value: string; label: string }>;
  sch: TableInfo;
}

export interface OtherInput {
  name: string;
  label: string;
  type: "int" | "float" | "bool" | "str" | "SourceRef";
  required?: boolean;
  default?: unknown;
  sch: TableInfo;
}

export type ScalarFeatureType = "str" | "int" | "float" | "bool";

/** Typed arrays are distinct from the legacy single-choice `list` input. */
export interface CollectionInput {
  name: string;
  label: string;
  type: "collection";
  itemType: ScalarFeatureType;
  required?: boolean;
  default?: unknown;
  sch: TableInfo;
}

export type InputFeatures = Array<ListInput | OtherInput | CollectionInput>;

/** Existing entities already carry their attributes; only new annotation fields are editable. */
export function inputsForEntitySelection(
  inputs: InputFeatures,
  selectedEntityId: string,
): InputFeatures {
  return selectedEntityId === "new"
    ? inputs
    : inputs.filter((input) => input.sch.group !== "entities");
}

function scalarMatches(type: ScalarFeatureType, value: unknown): boolean {
  if (type === "str") return typeof value === "string";
  if (type === "bool") return typeof value === "boolean";
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    (type !== "int" || Number.isSafeInteger(value))
  );
}

/** Parse a typed list without silently changing strings, numbers, or booleans. */
export function parseCollectionValue(
  text: string,
  itemType: ScalarFeatureType,
): { value: Array<string | number | boolean>; error: string } | { error: string } {
  try {
    const parsed: unknown = JSON.parse(text.trim() || "[]");
    if (!Array.isArray(parsed) || !parsed.every((item) => scalarMatches(itemType, item))) {
      return { error: `Enter a list of ${itemType} values.` };
    }
    return { value: parsed as Array<string | number | boolean>, error: "" };
  } catch {
    return { error: "Enter a valid list using square brackets." };
  }
}

export function validateEntityForm(
  inputs: InputFeatures,
  values: Record<string, Record<string, unknown>>,
): { success: boolean; errors: string[]; fieldErrors: FieldError[] } {
  const fieldErrors: FieldError[] = [];
  const push = (input: InputFeatures[number], problem: string) => {
    fieldErrors.push({
      name: input.name,
      sch: input.sch.name,
      message: `${humanizeFieldName(input.name)} ${problem}`,
    });
  };
  for (const input of inputs) {
    const tableValues = values[input.sch.name];
    const value = tableValues?.[input.name];
    if (value === undefined || value === null) {
      if (input.required) push(input, "is required");
      continue;
    }
    if (input.required && typeof value === "string" && value.trim() === "") {
      push(input, "is required");
    } else if (input.type === "collection") {
      if (!Array.isArray(value) || !value.every((item) => scalarMatches(input.itemType, item))) {
        push(input, `must be a list of ${input.itemType} values`);
      } else if (input.required && value.length === 0) {
        push(input, "is required");
      }
    } else if ((input.type === "str" || input.type === "list") && typeof value !== "string") {
      push(input, "must be a string");
    } else if (
      (input.type === "int" || input.type === "float") &&
      !scalarMatches(input.type, value)
    ) {
      push(input, input.type === "int" ? "must be a whole number" : "must be a finite number");
    } else if (input.type === "bool" && typeof value !== "boolean") {
      push(input, "must be a boolean");
    }
  }
  return {
    success: fieldErrors.length === 0,
    errors: fieldErrors.map((error) => error.message),
    fieldErrors,
  };
}
