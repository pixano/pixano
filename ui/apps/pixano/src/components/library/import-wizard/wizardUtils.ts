/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ImportPlanResponse, IoFinding } from "$lib/api/restTypes";

/** Friendly form fields the wizard collects before the Advanced overrides. */
export interface WizardFields {
  format: string; // "" = auto-detect
  source: string;
  name: string;
  mode: "create" | "overwrite";
  media: "embed" | "uri";
  episodes: string; // LeRobot: "0:4" or "1,3"
  maxFrames: string; // LeRobot: cap per episode
}

export const DEFAULT_FIELDS: WizardFields = {
  format: "",
  source: "",
  name: "",
  mode: "create",
  media: "embed",
  episodes: "",
  maxFrames: "",
};

/** A bare `org/name` Hugging Face dataset id (mirrors the backend rule). */
export function isHubId(source: string): boolean {
  const trimmed = source.trim();
  return /^[\w][\w.-]*\/[\w][\w.-]*$/.test(trimmed) && !trimmed.startsWith(".");
}

/** True when the LeRobot-specific fields should be shown. */
export function showsLerobotFields(fields: WizardFields): boolean {
  return fields.format === "lerobot" || (fields.format === "" && isHubId(fields.source));
}

/**
 * Build the spec payload: friendly fields first, the Advanced JSON overrides
 * merged on top (top-level keys shallow-merge into objects, like the backend).
 */
export function mergeSpec(fields: WizardFields, advancedJson: string): Record<string, unknown> {
  const spec: Record<string, unknown> = {};
  if (fields.format) spec.format = fields.format;
  if (fields.mode !== "create") spec.mode = fields.mode;
  if (fields.media !== "embed") spec.media = { mode: fields.media };
  const dataset: Record<string, unknown> = {};
  if (fields.name.trim()) dataset.name = fields.name.trim();
  if (Object.keys(dataset).length) spec.dataset = dataset;
  const options: Record<string, unknown> = {};
  if (fields.episodes.trim()) options.episodes = fields.episodes.trim();
  if (fields.maxFrames.trim()) options.max_frames_per_episode = Number(fields.maxFrames);
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

/** Source step gating: a source plus valid Advanced JSON. */
export function canAnalyze(fields: WizardFields, advancedJson: string): boolean {
  return fields.source.trim().length > 0 && !parseAdvancedSpec(advancedJson).error;
}
