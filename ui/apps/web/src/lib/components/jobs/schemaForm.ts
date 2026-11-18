/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { JsonSchema } from "$lib/api/jobs";

/** What a field renders as. `unsupported` is shown, never hidden. */
export type FieldKind =
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "enum"
  | "array"
  | "choices"
  | "model"
  | "unsupported";

/** The models the inference serves, by task — what a model field offers. */
export type ServedModels = Record<string, string[]>;

const RENDERABLE = new Set(["string", "number", "integer", "boolean"]);

/**
 * Decide how to render one parameter.
 *
 * Optional parameters arrive from pydantic as `anyOf: [{type: x}, {type: "null"}]`, so the
 * null branch is looked through — otherwise every optional field would show as unsupported.
 */
export function fieldKind(schema: JsonSchema): FieldKind {
  if (schema.enum && schema.enum.length > 0) return "enum";
  if (modelTaskOf(schema)) return "model";

  const type = schema.type ?? nonNullType(schema.anyOf);
  if (type && RENDERABLE.has(type)) return type as FieldKind;
  // A list whose items are drawn from a fixed set — the media types a job covers — is a set
  // of boxes to tick, not text to type.
  if (type === "array" && schema.items?.enum && schema.items.enum.length > 0) return "choices";
  // A list of scalars — the record identifiers of a selection — is typed as text, one value
  // per comma. Anything else inside a list stays unsupported rather than half-rendered.
  if (type === "array" && schema.items && RENDERABLE.has(scalarType(schema.items) ?? ""))
    return "array";
  return "unsupported";
}

function scalarType(schema: JsonSchema): string | undefined {
  const type = schema.type ?? nonNullType(schema.anyOf);
  return type === "boolean" ? undefined : type;
}

function nonNullType(branches: JsonSchema[] | undefined): string | undefined {
  const usable = (branches ?? []).filter((branch) => branch.type && branch.type !== "null");
  return usable.length === 1 ? usable[0].type : undefined;
}

/** The inference task a model parameter belongs to, if it is one. */
export function modelTaskOf(schema: JsonSchema): string | undefined {
  return schema["x-pixano-model-task"] || undefined;
}

/** The inference tasks whose models a set of kinds asks for, each once. */
export function modelTasks(schemas: JsonSchema[]): string[] {
  const tasks = schemas.flatMap((schema) =>
    Object.values(schema.properties ?? {}).map(modelTaskOf),
  );
  return [...new Set(tasks.filter((task): task is string => task !== undefined))];
}

/**
 * Propose a served model in every model field still empty.
 *
 * The models arrive after the form is drawn, and a field the user already filled keeps what
 * they chose. The first model the inference lists is proposed: nothing in the job names one.
 */
export function proposeModels(
  schema: JsonSchema,
  values: Record<string, unknown>,
  served: ServedModels,
): Record<string, unknown> {
  const proposed = { ...values };
  for (const [name, field] of Object.entries(schema.properties ?? {})) {
    const task = modelTaskOf(field);
    const first = task ? served[task]?.[0] : undefined;
    if (first !== undefined && (proposed[name] === "" || proposed[name] === undefined)) {
      proposed[name] = first;
    }
  }
  return proposed;
}

/**
 * The models a model field lists: those served, and the value it holds if it is not one of
 * them — typed before the list arrived, say. Without it the list would show the first model
 * while the job ran with the typed one.
 */
export function modelOptions(served: string[], value: unknown): string[] {
  const current = typeof value === "string" ? value : "";
  return current !== "" && !served.includes(current) ? [current, ...served] : served;
}

/** The value a field starts at: its declared default, or an empty value of its kind. */
export function initialValue(schema: JsonSchema): unknown {
  // A list is edited as text, so its default — usually an empty list — becomes text too.
  if (fieldKind(schema) === "array")
    return schema.default === undefined ? "" : asText(schema.default);
  if (fieldKind(schema) === "choices")
    return Array.isArray(schema.default) ? [...(schema.default as unknown[])] : [];
  if (schema.default !== undefined) return schema.default;
  switch (fieldKind(schema)) {
    case "boolean":
      return false;
    case "enum":
      return schema.enum?.[0];
    case "array":
      return "";
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
    if (kind === "choices") {
      // Sent as ticked, an empty list included: leaving it out would let the declared default
      // run a job on media the user just unticked.
      params[name] = Array.isArray(value) ? value : [];
      continue;
    }
    if (kind === "array") {
      const items = listItems(value, field.items);
      if (items.length > 0) params[name] = items;
      continue;
    }
    params[name] = value;
  }
  return params;
}

/**
 * Split what the user typed for a list, and cast each item to what the list holds.
 *
 * An item that does not parse as a number is dropped, as a lone number field would be; the
 * backend refuses the whole job rather than guessing.
 */
function listItems(value: unknown, items: JsonSchema | undefined): unknown[] {
  const raw = Array.isArray(value)
    ? value.map(asText)
    : String(value)
        .split(",")
        .map((item) => item.trim());
  const kept = raw.filter((item) => item !== "");
  const type = items ? scalarType(items) : "string";
  if (type === "number" || type === "integer") {
    return kept.map(Number).filter((item) => !Number.isNaN(item));
  }
  return kept;
}

/** Which parameters must be filled in for the job to be accepted. */
export function requiredNames(schema: JsonSchema): Set<string> {
  return new Set(schema.required ?? []);
}

/** The required fields left empty, so the form can refuse before the server does. */
export function missingRequired(schema: JsonSchema, values: Record<string, unknown>): string[] {
  const params = toParams(schema, values);
  const missing = [...requiredNames(schema)].filter((name) => !(name in params));
  // A multiple choice the schema wants non-empty is as missing as a required field left blank:
  // sent empty, the backend refuses the whole job.
  const tooFew = Object.entries(schema.properties ?? {})
    .filter(([, field]) => fieldKind(field) === "choices" && (field.minItems ?? 0) > 0)
    .filter(([name]) => !Array.isArray(params[name]) || (params[name] as unknown[]).length === 0)
    .map(([name]) => name);
  return [...missing, ...tooFew.filter((name) => !missing.includes(name))];
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
  if (Array.isArray(value)) return value.map(asText).join(", ");
  return "";
}

/** Tick or untick one choice of a multiple-choice field, keeping the declared order. */
export function toggleChoice(schema: JsonSchema, value: unknown, choice: unknown): unknown[] {
  const ticked: unknown[] = Array.isArray(value) ? (value as unknown[]) : [];
  const next = ticked.includes(choice)
    ? ticked.filter((item) => item !== choice)
    : [...ticked, choice];
  const order = schema.items?.enum ?? [];
  return order.filter((item) => next.includes(item));
}

/**
 * What the user must confirm before the job runs: the texts of the parameters that destroy
 * something, for those set. A parameter declares it with `x-pixano-confirm` in its schema.
 */
export function confirmationsFor(schema: JsonSchema, values: Record<string, unknown>): string[] {
  return Object.entries(schema.properties ?? {})
    .filter(([name, field]) => field["x-pixano-confirm"] && Boolean(values[name]))
    .map(([, field]) => field["x-pixano-confirm"] as string);
}
