/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { JsonSchema } from "$lib/api/jobs";

/** What a field renders as. `unsupported` is shown, never hidden. */
export type FieldKind = "string" | "number" | "integer" | "boolean" | "enum" | "unsupported";

const RENDERABLE = new Set(["string", "number", "integer", "boolean"]);

/**
 * Decide how to render one parameter.
 *
 * Optional parameters arrive from pydantic as `anyOf: [{type: x}, {type: "null"}]`, so the
 * null branch is looked through — otherwise every optional field would show as unsupported.
 */
export function fieldKind(schema: JsonSchema): FieldKind {
  if (schema.enum && schema.enum.length > 0) return "enum";

  const type = schema.type ?? nonNullType(schema.anyOf);
  if (type && RENDERABLE.has(type)) return type as FieldKind;
  return "unsupported";
}

function nonNullType(branches: JsonSchema[] | undefined): string | undefined {
  const usable = (branches ?? []).filter((branch) => branch.type && branch.type !== "null");
  return usable.length === 1 ? usable[0].type : undefined;
}

/** The value a field starts at: its declared default, or an empty value of its kind. */
export function initialValue(schema: JsonSchema): unknown {
  if (schema.default !== undefined) return schema.default;
  switch (fieldKind(schema)) {
    case "boolean":
      return false;
    case "enum":
      return schema.enum?.[0];
    default:
      return "";
  }
}

/** Every parameter of a kind, with its initial value. */
export function initialValues(schema: JsonSchema): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(schema.properties ?? {}).map(([name, field]) => [name, initialValue(field)]),
  );
}

/**
 * Turn what the form holds into what the API expects.
 *
 * Inputs give back strings, so numbers are converted here. A field left empty is dropped
 * rather than sent as an empty string: the backend would refuse the type, whereas dropping
 * it lets the declared default apply — which is what an untouched field means.
 */
export function toParams(
  schema: JsonSchema,
  values: Record<string, unknown>,
): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const [name, field] of Object.entries(schema.properties ?? {})) {
    const value = values[name];
    if (value === "" || value === undefined || value === null) continue;

    const kind = fieldKind(field);
    if (kind === "number" || kind === "integer") {
      const parsed = Number(value);
      if (!Number.isNaN(parsed)) params[name] = parsed;
      continue;
    }
    params[name] = value;
  }
  return params;
}

/** Which parameters must be filled in for the job to be accepted. */
export function requiredNames(schema: JsonSchema): Set<string> {
  return new Set(schema.required ?? []);
}

/** The required fields left empty, so the form can refuse before the server does. */
export function missingRequired(schema: JsonSchema, values: Record<string, unknown>): string[] {
  const params = toParams(schema, values);
  return [...requiredNames(schema)].filter((name) => !(name in params));
}

/**
 * Render a field value as text.
 *
 * Values arrive as `unknown` — they come from a schema the frontend does not control. Only
 * scalars have a sensible textual form; anything else would stringify as `[object Object]`
 * and put nonsense in an input, so it shows as empty and the field reports it cannot render.
 */
export function asText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}
