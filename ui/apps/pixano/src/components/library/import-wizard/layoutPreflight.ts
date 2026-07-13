/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Client-side folder-layout preflight for raw-media imports.
 *
 * Mirrors the backend's media-only discovery (`media_only.py`) over the picked
 * FileList so layout problems surface BEFORE gigabytes upload, not after. The
 * rules must stay in lockstep with the backend: split vocabulary, one media
 * kind per folder, per-view subfolders matched by stem, snake_case view names.
 */

/** What the user is building — maps 1:1 onto the backend workspace values. */
export type RawUseCase = "image" | "video" | "image_vqa" | "image_text_entity_linking";

/** On-disk media kinds the media-only importer scans. */
export type MediaFileKind = "image" | "video" | "text";

/** File extensions per media kind (mirrors `media_only.py` suffix sets). */
export const FILE_KIND_EXTENSIONS: Record<MediaFileKind, string[]> = {
  image: [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
  video: [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".vob"],
  text: [".txt", ".md"],
};

/** The media kinds each use case imports (MEL pairs images with texts). */
export const USE_CASE_FILE_KINDS: Record<RawUseCase, MediaFileKind[]> = {
  image: ["image"],
  video: ["video"],
  image_vqa: ["image"],
  image_text_entity_linking: ["image", "text"],
};

/** Split folder vocabulary (mirrors `_SPLIT_DIR_NAMES`). */
const SPLIT_DIR_NAMES = new Set([
  "train",
  "training",
  "val",
  "valid",
  "validation",
  "test",
  "testing",
]);

/** Classify a file name by extension (case-insensitive); null = not media. */
export function classifyMediaName(name: string): MediaFileKind | null {
  const lower = name.toLowerCase();
  for (const [kind, extensions] of Object.entries(FILE_KIND_EXTENSIONS)) {
    if (extensions.some((ext) => lower.endsWith(ext))) return kind as MediaFileKind;
  }
  return null;
}

/** True when a file belongs to the use case's upload (drives the upload filter). */
export function matchesUseCase(name: string, useCase: RawUseCase): boolean {
  const kind = classifyMediaName(name);
  return kind !== null && USE_CASE_FILE_KINDS[useCase].includes(kind);
}

/** Mirror of the backend's `to_snake_case` (folder → view name). */
export function toSnakeCase(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export interface LayoutFinding {
  code: string;
  severity: "error" | "warning";
  message: string;
}

export interface LayoutView {
  name: string;
  kind: MediaFileKind;
  fileCount: number;
}

export interface LayoutSplit {
  name: string;
  recordCount: number;
}

/** What the preflight derived from the picked folder. */
export interface LayoutPreflight {
  views: LayoutView[];
  splits: LayoutSplit[];
  totalRecords: number;
  keptFiles: number;
  ignoredFiles: number;
  findings: LayoutFinding[];
  ok: boolean;
}

interface KeptFile {
  segments: string[]; // path segments inside the picked folder
  kind: MediaFileKind;
}

/**
 * Derive the layout the backend will discover from the picked selection.
 *
 * `entries` are the files' paths inside the picked folder (the folder's own
 * name already stripped, as `splitFolderSelection` does). Only files matching
 * the use case's media kinds are laid out — everything else is counted as
 * ignored, exactly like the upload filter drops it.
 */
export function preflightLayout(
  entries: readonly { relPath: string }[],
  useCase: RawUseCase,
): LayoutPreflight {
  const findings: LayoutFinding[] = [];
  const allowed = USE_CASE_FILE_KINDS[useCase];
  const kept: KeptFile[] = [];
  let ignoredFiles = 0;
  const wrongKindCounts = new Map<MediaFileKind, number>();

  for (const entry of entries) {
    const segments = entry.relPath.split("/").filter(Boolean);
    if (!segments.length || segments.some((segment) => segment.startsWith("."))) {
      ignoredFiles += 1; // hidden segments mirror the backend's dot-dir skip
      continue;
    }
    const kind = classifyMediaName(segments[segments.length - 1]);
    if (kind === null) {
      ignoredFiles += 1;
      continue;
    }
    if (!allowed.includes(kind)) {
      ignoredFiles += 1;
      wrongKindCounts.set(kind, (wrongKindCounts.get(kind) ?? 0) + 1);
      continue;
    }
    kept.push({ segments, kind });
  }

  for (const [kind, count] of wrongKindCounts) {
    findings.push({
      code: "ignored_files",
      severity: "warning",
      message: `${count} ${kind} file${count === 1 ? "" : "s"} will not be uploaded for this use case.`,
    });
  }

  if (!kept.length) {
    findings.push({
      code: "no_media_found",
      severity: "error",
      message: "The selected folder has no importable media files for this use case.",
    });
    return result([], [], 0, kept.length, ignoredFiles, findings);
  }

  // Split detection at the root (all-or-none, like the backend).
  const rootDirs = new Map<string, KeptFile[]>();
  const rootFiles: KeptFile[] = [];
  for (const file of kept) {
    if (file.segments.length === 1) rootFiles.push(file);
    else {
      const dir = file.segments[0];
      rootDirs.set(dir, [...(rootDirs.get(dir) ?? []), file]);
    }
  }
  const splitLike = [...rootDirs.keys()].filter((dir) => SPLIT_DIR_NAMES.has(dir.toLowerCase()));
  if (splitLike.length && splitLike.length !== rootDirs.size) {
    findings.push({
      code: "ambiguous_media_layout",
      severity: "error",
      message:
        "Folders mix split names (train/val/test) with other media folders; " +
        "use only split folders, or only view folders.",
    });
    return result([], [], 0, kept.length, ignoredFiles, findings);
  }
  const usesSplits = splitLike.length > 0;
  if (usesSplits && rootFiles.length) {
    findings.push({
      code: "files_outside_splits",
      severity: "warning",
      message:
        `${rootFiles.length} file${rootFiles.length === 1 ? "" : "s"} at the folder root ` +
        "are ignored because the folder has split subfolders.",
    });
  }

  const splitInputs: { name: string; files: KeptFile[] }[] = usesSplits
    ? [...rootDirs.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([name, files]) => ({
          name,
          files: files.map((file) => ({ ...file, segments: file.segments.slice(1) })),
        }))
    : [{ name: "default", files: kept }];

  const splits: LayoutSplit[] = [];
  let referenceViews: Map<string, { kind: MediaFileKind; fileCount: number }> | null = null;
  const viewTotals = new Map<string, { kind: MediaFileKind; fileCount: number }>();

  for (const split of splitInputs) {
    const splitViews = splitLayout(split.name, split.files, useCase, findings);
    if (splitViews === null) {
      return result([], [], 0, kept.length, ignoredFiles, findings);
    }
    if (referenceViews === null) {
      referenceViews = splitViews.views;
    } else if (!sameViewSets(referenceViews, splitViews.views)) {
      findings.push({
        code: "inconsistent_split_views",
        severity: "error",
        message:
          `Split '${split.name}' implies different views than the other splits; ` +
          "make every split's folders identical.",
      });
      return result([], [], 0, kept.length, ignoredFiles, findings);
    }
    for (const [name, view] of splitViews.views) {
      const total = viewTotals.get(name) ?? { kind: view.kind, fileCount: 0 };
      total.fileCount += view.fileCount;
      viewTotals.set(name, total);
    }
    splits.push({ name: split.name, recordCount: splitViews.recordCount });
  }

  const views: LayoutView[] = [...viewTotals.entries()].map(([name, view]) => ({
    name,
    kind: view.kind,
    fileCount: view.fileCount,
  }));

  if (useCase === "image_text_entity_linking") {
    const textViews = views.filter((view) => view.kind === "text").length;
    const imageViews = views.filter((view) => view.kind === "image").length;
    if (textViews !== 1 || imageViews < 1) {
      findings.push({
        code: "mel_needs_image_and_text",
        severity: "error",
        message:
          "Image–text linking needs one text folder and at least one image folder " +
          "(e.g. image/ + text/), with files matched by name.",
      });
    }
  }

  const totalRecords = splits.reduce((sum, split) => sum + split.recordCount, 0);
  return result(views, splits, totalRecords, kept.length, ignoredFiles, findings);
}

/** One split's views + record count, or null on a blocking ambiguity. */
function splitLayout(
  splitName: string,
  files: KeptFile[],
  useCase: RawUseCase,
  findings: LayoutFinding[],
): { views: Map<string, { kind: MediaFileKind; fileCount: number }>; recordCount: number } | null {
  const where = splitName === "default" ? "the folder" : `'${splitName}/'`;
  const direct = files.filter((file) => file.segments.length === 1);
  const inDirs = files.filter((file) => file.segments.length > 1);

  if (direct.length && inDirs.length) {
    findings.push({
      code: "ambiguous_media_layout",
      severity: "error",
      message:
        `Media files sit both directly in ${where} and inside subfolders; ` +
        "move them all into view folders, or all at one level.",
    });
    return null;
  }

  if (!inDirs.length) {
    // Flat folder: one view named after the sole media kind.
    const kind = soleKind(direct, where, useCase, findings);
    if (kind === null) return null;
    if (
      !uniqueStems(
        direct.map((file) => stemOf(file.segments)),
        where,
        findings,
      )
    )
      return null;
    return {
      views: new Map([[kind, { kind, fileCount: direct.length }]]),
      recordCount: direct.length,
    };
  }

  // Per-view subfolders, stem-matched into records.
  const byDir = new Map<string, KeptFile[]>();
  for (const file of inDirs) {
    byDir.set(file.segments[0], [...(byDir.get(file.segments[0]) ?? []), file]);
  }
  const views = new Map<string, { kind: MediaFileKind; fileCount: number }>();
  const keysByView = new Map<string, Set<string>>();
  const namedDirs = new Map<string, string>();
  for (const [dir, dirFiles] of [...byDir.entries()].sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    const kind = soleKind(dirFiles, `'${dir}/'`, useCase, findings);
    if (kind === null) return null;
    const name = toSnakeCase(dir);
    if (views.has(name)) {
      findings.push({
        code: "view_name_collision",
        severity: "error",
        message: `Folders '${namedDirs.get(name)}' and '${dir}' both map to view '${name}'; rename one.`,
      });
      return null;
    }
    if (SPLIT_DIR_NAMES.has(name)) {
      findings.push({
        code: "view_name_reserved",
        severity: "error",
        message: `View folder '${dir}' collides with the split names (train/val/test…); rename it.`,
      });
      return null;
    }
    const keys = dirFiles.map((file) => stemOf(file.segments.slice(1)));
    if (!uniqueStems(keys, `'${dir}/'`, findings)) return null;
    views.set(name, { kind, fileCount: dirFiles.length });
    keysByView.set(name, new Set(keys));
    namedDirs.set(name, dir);
  }

  const allKeys = new Set<string>();
  for (const keys of keysByView.values()) for (const key of keys) allKeys.add(key);
  let missing = 0;
  for (const keys of keysByView.values()) missing += allKeys.size - keys.size;
  if (missing > 0) {
    findings.push({
      code: "missing_view_file",
      severity: "warning",
      message:
        `${missing} record${missing === 1 ? " is" : "s are"} missing a file in one of the views ` +
        "(matched by file name); those views are omitted for those records.",
    });
  }
  return { views, recordCount: allKeys.size };
}

function soleKind(
  files: KeptFile[],
  where: string,
  useCase: RawUseCase,
  findings: LayoutFinding[],
): MediaFileKind | null {
  const kinds = [...new Set(files.map((file) => file.kind))].sort();
  if (kinds.length === 1) return kinds[0];
  const hint =
    useCase === "image_text_entity_linking"
      ? " For image–text linking, put images and texts in separate view folders (image/ + text/)."
      : "";
  findings.push({
    code: "mixed_media_kinds",
    severity: "error",
    message: `${where} mixes ${kinds.join(" and ")} files; keep one media kind per folder.${hint}`,
  });
  return null;
}

function uniqueStems(keys: string[], where: string, findings: LayoutFinding[]): boolean {
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const key of keys) {
    if (seen.has(key)) duplicates.add(key);
    seen.add(key);
  }
  if (!duplicates.size) return true;
  const sample = [...duplicates][0];
  findings.push({
    code: "duplicate_view_stem",
    severity: "error",
    message: `'${sample}' appears with several extensions under ${where}; file names must be unique per view.`,
  });
  return false;
}

/** The stem-match key: the path inside the view folder, without the extension. */
function stemOf(segments: string[]): string {
  const path = segments.join("/");
  const dot = path.lastIndexOf(".");
  return dot > path.lastIndexOf("/") ? path.slice(0, dot) : path;
}

function sameViewSets(
  left: Map<string, { kind: MediaFileKind }>,
  right: Map<string, { kind: MediaFileKind }>,
): boolean {
  if (left.size !== right.size) return false;
  for (const [name, view] of left) {
    if (right.get(name)?.kind !== view.kind) return false;
  }
  return true;
}

function result(
  views: LayoutView[],
  splits: LayoutSplit[],
  totalRecords: number,
  keptFiles: number,
  ignoredFiles: number,
  findings: LayoutFinding[],
): LayoutPreflight {
  return {
    views,
    splits,
    totalRecords,
    keptFiles,
    ignoredFiles,
    findings,
    ok: !findings.some((finding) => finding.severity === "error"),
  };
}
