/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The raw-media schema builder: pure helpers turning wizard fields into a spec `schema`. */

import type { LayoutPreflight, RawTask } from "./layoutPreflight";

export type RawFramesMode = "extract" | "reference";
export type AttrType = "str" | "int" | "float" | "bool";

export interface AttrRow {
  name: string;
  type: AttrType;
  list: boolean;
  required: boolean;
  defaultValue: string;
}

export interface RawFields {
  task: RawTask;
  framesMode: RawFramesMode; // video only, files encoding
  maxFrames: string; // video only
  fps: string; // video only, folders encoding (stamps frame timestamps)
  recordAttrs: AttrRow[];
  entityAttrs: AttrRow[];
  annotations: string[];
  layout: LayoutPreflight | null; // derived from the picked folder before upload
}

/** The task cards: labels + the folder layout each one expects. */
export const TASK_CARDS: {
  task: RawTask;
  title: string;
  blurb: string;
  layoutHint: string;
}[] = [
  {
    task: "image",
    title: "Image annotation",
    blurb: "Draw boxes, masks, and polygons on images — one or several views per record.",
    layoutHint:
      "photos/\n├─ a.jpg  b.jpg …      (single view)\n└─ or left/ right/ …   (views, same file names pair up)",
  },
  {
    task: "video",
    title: "Video annotation",
    blurb: "Track objects across frames — videos import as annotatable frame sequences.",
    layoutHint:
      "clips/\n├─ v1.mp4  v2.mp4 …    (video files)\n├─ or v1/ v2/ …        (one folder of frame images per video)\n└─ or front/ side/ …   (views, same names pair up)",
  },
  {
    task: "image_vqa",
    title: "Visual Q&A",
    blurb: "Ask and answer questions about images — conversations attach to each record.",
    layoutHint: "photos/\n└─ a.jpg  b.jpg …      (questions are added in Pixano)",
  },
  {
    task: "image_text_entity_linking",
    title: "Image–text linking",
    blurb: "Link mentions in a text to regions in an image (multimodal entity linking).",
    layoutHint: "pairs/\n├─ image/  a.jpg  b.jpg\n└─ text/   a.txt  b.txt  (same names pair up)",
  },
];

/** Annotation slots pre-selected per task (what most users annotate). */
export const DEFAULT_ANNOTATIONS: Record<RawTask, string[]> = {
  image: ["bbox", "mask"],
  video: ["bbox", "mask", "tracklet"],
  image_vqa: ["message"],
  image_text_entity_linking: ["text_span", "bbox", "mask"],
};

/** Annotation slots offered per task (the declarative-dialect subset that fits each). */
export const ANNOTATION_CHOICES: Record<RawTask, string[]> = {
  image: ["bbox", "mask", "multi_path"],
  video: ["bbox", "mask", "multi_path", "tracklet"],
  image_vqa: ["message", "bbox", "mask"],
  image_text_entity_linking: ["text_span", "bbox", "mask"],
};

/**
 * Slots the task cannot work without (always included). A non-empty
 * `schema.annotations` REPLACES the workspace preset's slots backend-side, so
 * the wizard must always re-list these.
 */
export const LOCKED_ANNOTATIONS: Record<RawTask, string[]> = {
  image: [],
  video: ["tracklet"],
  image_vqa: ["message"],
  image_text_entity_linking: ["text_span"],
};

export const ATTR_TYPES: AttrType[] = ["str", "int", "float", "bool"];

export const ATTR_TYPE_LABELS: Record<AttrType, string> = {
  str: "String",
  int: "Integer",
  float: "Float",
  bool: "Boolean",
};

export const ANNOTATION_TOOLS: Record<string, { label: string; description: string }> = {
  bbox: { label: "Bounding boxes", description: "Rectangular object regions." },
  mask: { label: "Masks", description: "Pixel-level segmentation." },
  multi_path: { label: "Polygons & lines", description: "Polygon and polyline annotations." },
  tracklet: { label: "Object tracks", description: "Object identities across frames." },
  message: {
    label: "Questions & answers",
    description: "Image question-answer pairs.",
  },
  text_span: { label: "Text spans", description: "Text spans linked to image regions." },
};

/** Only supported tools are emitted, with task requirements included automatically. */
export function annotationsForTask(task: RawTask, selected: string[]): string[] {
  return ANNOTATION_CHOICES[task].filter(
    (slot) => selected.includes(slot) || LOCKED_ANNOTATIONS[task].includes(slot),
  );
}

export const DEFAULT_RAW_FIELDS: RawFields = {
  task: "image",
  framesMode: "extract",
  maxFrames: "",
  fps: "",
  recordAttrs: [],
  entityAttrs: [],
  annotations: [...DEFAULT_ANNOTATIONS.image],
  layout: null,
};

const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

/** Parse a default-value string as the attribute type; undefined when invalid. */
export function parseTypedValue(type: AttrType, value: string): unknown {
  const text = value.trim();
  if (type === "str") return text;
  if (type === "bool") {
    if (text === "true") return true;
    if (text === "false") return false;
    return undefined;
  }
  const numeric = Number(text);
  if (type === "int") {
    return /^-?\d+$/.test(text) && Number.isSafeInteger(numeric) ? numeric : undefined;
  }
  return /^-?(\d+\.?\d*|\.\d+)$/.test(text) && Number.isFinite(numeric) ? numeric : undefined;
}

/** Parse a comma-separated list default (`a, b`); undefined when any element is invalid. */
export function parseTypedListValue(type: AttrType, value: string): unknown[] | undefined {
  const parts = value
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  const parsed = parts.map((part) => parseTypedValue(type, part));
  return parsed.some((item) => item === undefined) ? undefined : parsed;
}

/** Validate one attrs editor's rows; returns "" when they compile cleanly. */
export function validateAttrRows(rows: AttrRow[], label = "Attribute"): string {
  const seen = new Set<string>();
  for (const row of rows) {
    if (!NAME_PATTERN.test(row.name)) {
      return `${label} '${row.name || "(empty)"}': use snake_case names (letters, digits, _).`;
    }
    if (seen.has(row.name)) return `${label} '${row.name}' is declared twice.`;
    seen.add(row.name);
    if (!row.required && row.defaultValue.trim()) {
      const parsed = row.list
        ? parseTypedListValue(row.type, row.defaultValue)
        : parseTypedValue(row.type, row.defaultValue);
      if (parsed === undefined) {
        const shape = row.list ? `comma-separated ${row.type} list` : row.type;
        return `${label} '${row.name}': default '${row.defaultValue}' is not a valid ${shape}.`;
      }
    }
  }
  return "";
}

/** Validate source-side video options; hidden reference-mode options do not apply. */
export function validateRawVideoOptions(raw: RawFields): string {
  if (raw.task !== "video") return "";
  const folders = raw.layout?.ok === true && raw.layout.encoding === "folders";
  if (!folders && raw.framesMode === "reference") return "";
  if (
    raw.maxFrames.trim() &&
    (!/^\d+$/.test(raw.maxFrames.trim()) ||
      !Number.isSafeInteger(Number(raw.maxFrames)) ||
      Number(raw.maxFrames) <= 0)
  ) {
    return "Max frames per video must be a positive whole number.";
  }
  if (raw.fps.trim() && (!Number.isFinite(Number(raw.fps)) || !(Number(raw.fps) > 0))) {
    return "FPS must be a positive number.";
  }
  return "";
}

/** Validate only the annotation pane, independently of the source controls. */
export function validateRawSchemaFields(raw: RawFields): string {
  if (!annotationsForTask(raw.task, raw.annotations).length) {
    return "Select at least one annotation tool.";
  }
  const recordError = validateAttrRows(raw.recordAttrs, "Record attribute");
  if (recordError) return recordError;
  return validateAttrRows(raw.entityAttrs, "Object attribute");
}

/** One validation message for the whole raw form; "" when analyzable. */
export function validateRawFields(raw: RawFields): string {
  return validateRawVideoOptions(raw) || validateRawSchemaFields(raw);
}

/** Serialize an attrs editor's rows using the shared ImportSpec schema dialect. */
export function attrsPayload(rows: AttrRow[]): Record<string, unknown> {
  const attrs: Record<string, unknown> = {};
  for (const row of rows) {
    const attr: Record<string, unknown> = { type: row.type };
    if (row.list) attr.collection = true;
    if (row.required) attr.required = true;
    else if (row.defaultValue.trim()) {
      attr.default = row.list
        ? parseTypedListValue(row.type, row.defaultValue)
        : parseTypedValue(row.type, row.defaultValue);
    }
    attrs[row.name] = attr;
  }
  return attrs;
}

/**
 * Compile the raw form into spec fragments.
 *
 * The workspace is always the task — that is what routes the dataset to
 * the right annotation UI. Views are declared only when the preflight found
 * several (per-view folders); single-view sources rely on backend inference.
 * Annotations are always sent: a non-empty list replaces the preset's slots,
 * so the form is the single source of truth for what gets created.
 */
export function buildRawSchemaSpec(raw: RawFields): {
  schema: Record<string, unknown>;
  workspace: string;
  options?: Record<string, unknown>;
} {
  const schema: Record<string, unknown> = {};

  const encoding = raw.task === "video" && raw.layout?.ok ? raw.layout.encoding : "files";
  const layoutViews = raw.layout?.ok ? raw.layout.views : [];
  if (layoutViews.length >= 2) {
    const videoKind =
      encoding === "folders" || raw.framesMode !== "reference" ? "sequence_frames" : "video";
    schema.views = Object.fromEntries(
      layoutViews.map((view) => [
        view.name,
        // Frame-folder views hold image files client-side but ARE sequence frames.
        { kind: encoding === "folders" || view.kind === "video" ? videoKind : view.kind },
      ]),
    );
  }

  if (raw.recordAttrs.length) schema.record = { attrs: attrsPayload(raw.recordAttrs) };
  if (raw.entityAttrs.length) schema.entity = { attrs: attrsPayload(raw.entityAttrs) };
  const annotations = annotationsForTask(raw.task, raw.annotations);
  if (annotations.length) schema.annotations = annotations;

  const options: Record<string, unknown> = {};
  if (raw.task === "video" && encoding === "folders") {
    options.frames = "folders";
    if (raw.maxFrames.trim()) options.max_frames_per_video = Number(raw.maxFrames.trim());
    if (raw.fps.trim()) options.fps = Number(raw.fps.trim());
  } else if (raw.task === "video") {
    if (raw.framesMode === "reference") {
      options.frames = "reference";
    } else {
      if (raw.maxFrames.trim()) options.max_frames_per_video = Number(raw.maxFrames.trim());
      if (raw.fps.trim()) options.fps = Number(raw.fps.trim()); // extraction sampling rate
    }
  }

  return {
    schema,
    workspace: raw.task,
    options: Object.keys(options).length ? options : undefined,
  };
}
