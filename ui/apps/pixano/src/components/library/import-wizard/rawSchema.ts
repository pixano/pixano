/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The raw-media schema builder: pure helpers turning wizard fields into a spec `schema`. */

export type RawMediaKind = "images" | "videos" | "texts";
export type RawViewsMode = "auto" | "named";
export type RawFramesMode = "extract" | "reference";
export type EntityAttrType = "str" | "int" | "float" | "bool";

export interface EntityAttrRow {
  name: string;
  type: EntityAttrType;
  list: boolean;
  required: boolean;
  defaultValue: string;
}

export interface RawFields {
  kind: RawMediaKind;
  viewsMode: RawViewsMode;
  viewNames: string; // comma-separated, used when viewsMode === "named"
  framesMode: RawFramesMode; // videos only
  maxFrames: string; // videos, extract mode
  entityAttrs: EntityAttrRow[];
  annotations: string[];
}

/** Annotation slots pre-selected per media kind (what most users annotate). */
export const DEFAULT_ANNOTATIONS: Record<RawMediaKind, string[]> = {
  images: ["bbox", "mask", "keypoint", "classification"],
  videos: ["bbox", "mask", "keypoint", "tracklet"],
  texts: ["text_span", "classification"],
};

/** Annotation slots offered per media kind (the declarative-dialect subset that fits each). */
export const ANNOTATION_CHOICES: Record<RawMediaKind, string[]> = {
  images: ["bbox", "mask", "keypoint", "multi_path", "classification", "relation", "message"],
  videos: ["bbox", "mask", "keypoint", "multi_path", "classification", "tracklet", "relation"],
  texts: ["text_span", "classification", "message", "relation"],
};

/** File extensions the backend imports per media kind (mirrors media_only.py). */
export const MEDIA_KIND_EXTENSIONS: Record<RawMediaKind, string[]> = {
  images: [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
  videos: [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".vob"],
  texts: [".txt", ".md"],
};

/** True when a file name carries one of the media kind's extensions (case-insensitive). */
export function matchesMediaKind(name: string, kind: RawMediaKind): boolean {
  const lower = name.toLowerCase();
  return MEDIA_KIND_EXTENSIONS[kind].some((ext) => lower.endsWith(ext));
}

export const ENTITY_ATTR_TYPES: EntityAttrType[] = ["str", "int", "float", "bool"];

export const DEFAULT_RAW_FIELDS: RawFields = {
  kind: "images",
  viewsMode: "auto",
  viewNames: "",
  framesMode: "extract",
  maxFrames: "",
  entityAttrs: [],
  annotations: [...DEFAULT_ANNOTATIONS.images],
};

const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

/** Parse the comma-separated view names input; names must be snake_case and unique. */
export function parseViewNames(input: string): { names: string[]; error: string } {
  const names = input
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name.length > 0);
  for (const name of names) {
    if (!NAME_PATTERN.test(name)) {
      return { names: [], error: `View '${name}': use snake_case names (letters, digits, _).` };
    }
  }
  if (new Set(names).size !== names.length) {
    return { names: [], error: "View names must be unique." };
  }
  return { names, error: "" };
}

/** Validate the entity-attribute rows; returns "" when they compile cleanly. */
export function validateEntityAttrs(rows: EntityAttrRow[]): string {
  const seen = new Set<string>();
  for (const row of rows) {
    if (!NAME_PATTERN.test(row.name)) {
      return `Attribute '${row.name || "(empty)"}': use snake_case names (letters, digits, _).`;
    }
    if (seen.has(row.name)) return `Attribute '${row.name}' is declared twice.`;
    seen.add(row.name);
    if (row.defaultValue.trim() && parseTypedValue(row.type, row.defaultValue) === undefined) {
      return `Attribute '${row.name}': default '${row.defaultValue}' is not a valid ${row.type}.`;
    }
  }
  return "";
}

/** Parse a default-value string as the attribute type; undefined when invalid. */
export function parseTypedValue(type: EntityAttrType, value: string): unknown {
  const text = value.trim();
  if (type === "str") return text;
  if (type === "bool") {
    if (text === "true") return true;
    if (text === "false") return false;
    return undefined;
  }
  if (type === "int") return /^-?\d+$/.test(text) ? Number(text) : undefined;
  return /^-?(\d+\.?\d*|\.\d+)$/.test(text) ? Number(text) : undefined;
}

/** One validation message for the whole raw form; "" when analyzable. */
export function validateRawFields(raw: RawFields): string {
  if (raw.kind === "images" && raw.viewsMode === "named") {
    const { names, error } = parseViewNames(raw.viewNames);
    if (error) return error;
    if (!names.length) return "Name at least one view, or switch back to automatic views.";
  }
  if (raw.kind === "videos" && raw.maxFrames.trim() && !/^\d+$/.test(raw.maxFrames.trim())) {
    return "Max frames per video must be a whole number.";
  }
  return validateEntityAttrs(raw.entityAttrs);
}

/**
 * Compile the raw form into spec fragments.
 *
 * Views are declared only when the user names them — otherwise the backend
 * infers them from the folder layout (and the confirmed schema is shown on
 * the review step). Note: an empty annotations selection keeps the workspace
 * preset's slots (the backend treats [] as "no override").
 */
export function buildRawSchemaSpec(raw: RawFields): {
  schema: Record<string, unknown>;
  workspace?: string;
  options?: Record<string, unknown>;
} {
  const schema: Record<string, unknown> = {};

  if (raw.kind === "images" && raw.viewsMode === "named") {
    const { names } = parseViewNames(raw.viewNames);
    if (names.length) {
      schema.views = Object.fromEntries(names.map((name) => [name, "image"]));
    }
  }

  if (raw.entityAttrs.length) {
    const attrs: Record<string, unknown> = {};
    for (const row of raw.entityAttrs) {
      const attr: Record<string, unknown> = { type: row.type };
      if (row.list) attr.collection = true;
      if (row.required) attr.required = true;
      else if (row.defaultValue.trim()) attr.default = parseTypedValue(row.type, row.defaultValue);
      attrs[row.name] = attr;
    }
    schema.entity = { attrs };
  }

  if (raw.annotations.length) schema.annotations = [...raw.annotations];

  const options: Record<string, unknown> = {};
  if (raw.kind === "videos") {
    if (raw.framesMode === "reference") options.frames = "reference";
    else if (raw.maxFrames.trim()) options.max_frames_per_video = Number(raw.maxFrames.trim());
  }

  return {
    schema,
    workspace: raw.kind === "images" ? "image" : raw.kind === "videos" ? "video" : undefined,
    options: Object.keys(options).length ? options : undefined,
  };
}
