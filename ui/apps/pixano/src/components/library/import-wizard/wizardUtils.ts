/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  buildRawSchemaSpec,
  DEFAULT_RAW_FIELDS,
  validateRawFields,
  type RawFields,
} from "./rawSchema";
import type {
  ImportPlanResponse,
  InferredSchemaResponse,
  IoFinding,
  IoJobResponse,
  SchemaDescriptor,
} from "$lib/api/restTypes";

/** What the user is importing — the wizard leads with intent, not format names. */
export type ImportIntent = "raw" | "pixano_jsonl" | "coco" | "lerobot" | "auto";

/** The backend format each intent maps to ("" = auto-detect). */
export function intentToFormat(intent: ImportIntent): string {
  if (intent === "raw" || intent === "pixano_jsonl") return "pixano_jsonl";
  if (intent === "auto") return "";
  return intent;
}

/** Friendly form fields the wizard collects before the Advanced overrides. */
export interface WizardFields {
  intent: ImportIntent;
  source: string; // staged upload path or a Hugging Face id — never shown as-is
  sourceLabel: string; // the uploaded folder's name (display + default dataset name)
  name: string;
  mode: "create" | "overwrite";
  media: "embed" | "uri";
  episodes: string; // LeRobot: "0:4" or "1,3"
  maxFrames: string; // LeRobot: cap per episode
  raw: RawFields; // raw-media schema builder state
}

export const DEFAULT_FIELDS: WizardFields = {
  intent: "auto",
  source: "",
  sourceLabel: "",
  name: "",
  mode: "create",
  media: "embed",
  episodes: "",
  maxFrames: "",
  raw: structuredClone(DEFAULT_RAW_FIELDS),
};

/** A bare `org/name` Hugging Face dataset id (mirrors the backend rule). */
export function isHubId(source: string): boolean {
  const trimmed = source.trim();
  return /^[\w][\w.-]*\/[\w][\w.-]*$/.test(trimmed) && !trimmed.startsWith(".");
}

/** True when the LeRobot-specific fields should be shown. */
export function showsLerobotFields(fields: WizardFields): boolean {
  return fields.intent === "lerobot" || (fields.intent === "auto" && isHubId(fields.source));
}

/**
 * Build the spec payload: friendly fields first, the Advanced JSON overrides
 * merged on top (top-level keys shallow-merge into objects, like the backend).
 */
export function mergeSpec(fields: WizardFields, advancedJson: string): Record<string, unknown> {
  const spec: Record<string, unknown> = {};
  const format = intentToFormat(fields.intent);
  if (format) spec.format = format;
  if (fields.mode !== "create") spec.mode = fields.mode;
  if (fields.media !== "embed" && fields.intent !== "raw") spec.media = { mode: fields.media };
  const dataset: Record<string, unknown> = {};
  if (fields.name.trim()) dataset.name = fields.name.trim();
  else if (fields.sourceLabel.trim()) dataset.name = fields.sourceLabel.trim(); // staged dirs have opaque names
  const options: Record<string, unknown> = {};
  if (showsLerobotFields(fields)) {
    if (fields.episodes.trim()) options.episodes = fields.episodes.trim();
    if (fields.maxFrames.trim()) options.max_frames_per_episode = Number(fields.maxFrames);
  }
  if (fields.intent === "raw") {
    const raw = buildRawSchemaSpec(fields.raw);
    if (Object.keys(raw.schema).length) spec.schema = raw.schema;
    if (raw.workspace) dataset.workspace = raw.workspace;
    Object.assign(options, raw.options ?? {});
  }
  if (Object.keys(dataset).length) spec.dataset = dataset;
  if (Object.keys(options).length) spec.options = options;

  const advanced = parseAdvancedSpec(advancedJson);
  if (advanced.value) {
    for (const [key, value] of Object.entries(advanced.value)) {
      const existing = spec[key];
      if (isPlainObject(value) && isPlainObject(existing)) {
        spec[key] = { ...existing, ...value };
      } else {
        spec[key] = value;
      }
    }
  }
  return spec;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Parse the Advanced JSON textarea; empty input is valid (no overrides). */
export function parseAdvancedSpec(advancedJson: string): {
  value: Record<string, unknown> | null;
  error: string;
} {
  const text = advancedJson.trim();
  if (!text) return { value: null, error: "" };
  try {
    const parsed: unknown = JSON.parse(text);
    if (!isPlainObject(parsed)) {
      return { value: null, error: "The spec must be a JSON object (it mirrors dataset.yaml)." };
    }
    return { value: parsed, error: "" };
  } catch (err) {
    return { value: null, error: err instanceof Error ? err.message : "Invalid JSON." };
  }
}

/** Findings split by severity for the preview step. */
export function groupFindings(plan: ImportPlanResponse): {
  errors: IoFinding[];
  warnings: IoFinding[];
} {
  const findings = Object.values(plan.report?.findings ?? {});
  return {
    errors: findings.filter((finding) => finding.severity === "error"),
    warnings: findings.filter((finding) => finding.severity !== "error"),
  };
}

/** Human-readable byte size for the plan's media estimate. */
export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

/** A short location string for one finding sample. */
export function sampleLocation(sample: { file?: string | null; line?: number | null }): string {
  const file = sample.file ? sample.file.split("/").slice(-2).join("/") : "";
  return sample.line ? `${file}:${sample.line}` : file;
}

/** Source step gating: a source, valid Advanced JSON, and a clean raw form. */
export function canAnalyze(fields: WizardFields, advancedJson: string): boolean {
  if (!fields.source.trim() || parseAdvancedSpec(advancedJson).error) return false;
  return fields.intent !== "raw" || validateRawFields(fields.raw) === "";
}

/** One attribute chip of a schema entry. */
export interface SchemaAttr {
  name: string;
  type: string;
  collection: boolean;
  required: boolean;
}

/** One named schema element (a view, the record, the entity, an annotation slot). */
export interface SchemaEntry {
  name: string;
  base: string;
  attrs: SchemaAttr[];
}

/** One SchemaPanel section. */
export interface SchemaSection {
  title: string;
  entries: SchemaEntry[];
}

const SCHEMA_META_KEYS = new Set(["workspace", "views", "record", "entity"]);

function schemaEntry(name: string, descriptor: SchemaDescriptor): SchemaEntry {
  return {
    name,
    base: descriptor.base ?? "?",
    attrs: Object.entries(descriptor.fields ?? {}).map(([attrName, field]) => ({
      name: attrName,
      type: field.type ?? "?",
      collection: field.collection === true,
      required: field.required === true,
    })),
  };
}

/** Massage a plan's inferred_schema into ordered sections for the SchemaPanel. */
export function schemaSections(schema: InferredSchemaResponse): SchemaSection[] {
  const sections: SchemaSection[] = [];
  const views = Object.entries(schema.views ?? {}).map(([name, descriptor]) =>
    schemaEntry(name, descriptor),
  );
  if (views.length) sections.push({ title: "Views", entries: views });
  if (schema.record)
    sections.push({ title: "Record", entries: [schemaEntry("record", schema.record)] });
  if (schema.entity)
    sections.push({ title: "Entity", entries: [schemaEntry("entity", schema.entity)] });
  const annotations = Object.keys(schema)
    .filter((key) => !SCHEMA_META_KEYS.has(key) && isDescriptor(schema[key]))
    .sort()
    .map((slot) => schemaEntry(slot, schema[slot] as SchemaDescriptor));
  if (annotations.length) sections.push({ title: "Annotations", entries: annotations });
  return sections;
}

function isDescriptor(value: unknown): value is SchemaDescriptor {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** One background import tracked by the jobs tray. */
export interface ImportJobEntry {
  jobId: string;
  dataset: string;
  job: IoJobResponse;
  cancelRequested: boolean;
  dismissed: boolean;
}

const TERMINAL_STATUSES: ReadonlySet<string> = new Set([
  "done",
  "error",
  "cancelled",
  "interrupted",
  "rolled_back",
]);

/** True when the job will never progress again (polling can stop). */
export function isTerminalJob(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

/**
 * Merge a polled job into the tracked entries.
 *
 * Returns the new entries plus whether this update just crossed into a
 * SUCCESSFUL terminal state (the moment the library list must refresh).
 */
export function applyJobUpdate(
  entries: ImportJobEntry[],
  job: IoJobResponse,
): { entries: ImportJobEntry[]; completedNow: boolean } {
  let completedNow = false;
  const next = entries.map((entry) => {
    if (entry.jobId !== job.job_id) return entry;
    if (!isTerminalJob(entry.job.status) && (job.status === "done" || job.status === "cancelled")) {
      completedNow = true;
    }
    return { ...entry, job };
  });
  return { entries: next, completedNow };
}

/** Entries the tray should render (not dismissed). */
export function visibleJobEntries(entries: ImportJobEntry[]): ImportJobEntry[] {
  return entries.filter((entry) => !entry.dismissed);
}

/** Entries that still need polling. */
export function activeJobEntries(entries: ImportJobEntry[]): ImportJobEntry[] {
  return entries.filter((entry) => !isTerminalJob(entry.job.status));
}

/** A short human label for a tray entry's state. */
export function jobStateLabel(entry: ImportJobEntry): string {
  if (entry.job.status === "done") return "Imported";
  if (entry.job.status === "cancelled") return "Cancelled";
  if (entry.job.status === "error" || entry.job.status === "interrupted") return "Failed";
  if (entry.cancelRequested) return "Cancelling…";
  return entry.job.progress?.phase || "Running";
}
