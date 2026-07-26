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
  options: Array<{ value: string; label: string }>;
  sch: TableInfo;
}

export interface OtherInput {
  name: string;
  label: string;
  type: "int" | "float" | "bool" | "str" | "SourceRef";
  required?: boolean;
  sch: TableInfo;
}

export type InputFeatures = Array<ListInput | OtherInput>;

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
    if ((input.type === "str" || input.type === "list") && typeof value !== "string") {
      push(input, "must be a string");
    } else if ((input.type === "int" || input.type === "float") && typeof value !== "number") {
      push(input, "must be a number");
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
