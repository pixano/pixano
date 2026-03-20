/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BaseSchema } from "$lib/types/dataset";

export interface TableInfo {
  name: string;
  group: string;
  base_schema: BaseSchema;
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
): { success: boolean; errors: string[] } {
  const errors: string[] = [];
  for (const input of inputs) {
    const tableValues = values[input.sch.name];
    const value = tableValues?.[input.name];
    if (value === undefined || value === null) {
      if (input.required) errors.push(`${input.label} is required`);
      continue;
    }
    if ((input.type === "str" || input.type === "list") && typeof value !== "string") {
      errors.push(`${input.label} must be a string`);
    } else if ((input.type === "int" || input.type === "float") && typeof value !== "number") {
      errors.push(`${input.label} must be a number`);
    } else if (input.type === "bool" && typeof value !== "boolean") {
      errors.push(`${input.label} must be a boolean`);
    }
  }
  return { success: errors.length === 0, errors };
}
