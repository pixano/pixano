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
export type RawTask = "image" | "video" | "image_vqa" | "image_text_entity_linking";

/** On-disk media kinds the media-only importer scans. */
export type MediaFileKind = "image" | "video" | "text";

/** File extensions per media kind (mirrors `media_only.py` suffix sets). */
export const FILE_KIND_EXTENSIONS: Record<MediaFileKind, string[]> = {
  image: [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
  video: [".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".vob"],
  text: [".txt", ".md"],
};

/** The media kinds each task imports (MEL pairs images with texts). */
export const TASK_FILE_KINDS: Record<RawTask, MediaFileKind[]> = {
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

/** True when a file belongs to the task's upload (drives the upload filter). */
export function matchesTask(name: string, task: RawTask): boolean {
  const kind = classifyMediaName(name);
  return kind !== null && TASK_FILE_KINDS[task].includes(kind);
}

/**
 * How the video task's source encodes its videos: video FILES (.mp4 …) or one
 * FOLDER of pre-extracted frame images per video. Detected by the preflight;
 * always "files" for the other tasks.
 */
export type RawVideoEncoding = "files" | "folders";

/** The upload filter, encoding-aware: frame-folder videos upload images, not videos. */
export function matchesUpload(name: string, task: RawTask, encoding: RawVideoEncoding): boolean {
  if (task !== "video") return matchesTask(name, task);
  const kind = classifyMediaName(name);
  return kind === (encoding === "folders" ? "image" : "video");
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
  fileCount: number; // frame count in the folders encoding
  groupCount?: number; // video folders in this view (folders encoding only)
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
  encoding: RawVideoEncoding;
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
 * the task's media kinds are laid out — everything else is counted as
 * ignored, exactly like the upload filter drops it.
 */
export function preflightLayout(
  entries: readonly { relPath: string }[],
  task: RawTask,
): LayoutPreflight {
  const findings: LayoutFinding[] = [];
  const encoding = detectVideoEncoding(entries, task);
  if (encoding === null) {
    findings.push({
      code: "mixed_video_encodings",
      severity: "error",
      message:
        "The folder mixes video files and frame images; import either video files OR one folder " +
        "of frame images per video, not both.",
    });
    return result([], [], 0, 0, entries.length, findings, "files");
  }
  const allowed: MediaFileKind[] =
    task === "video" && encoding === "folders" ? ["image"] : TASK_FILE_KINDS[task];
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
      message: `${count} ${kind} file${count === 1 ? "" : "s"} will not be uploaded for this task.`,
    });
  }

  if (!kept.length) {
    findings.push({
      code: "no_media_found",
      severity: "error",
      message: "The selected folder has no importable media files for this task.",
    });
    return result([], [], 0, kept.length, ignoredFiles, findings, encoding);
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
    return result([], [], 0, kept.length, ignoredFiles, findings, encoding);
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
  let referenceViews: Map<string, SplitView> | null = null;
  const viewTotals = new Map<string, SplitView>();

  for (const split of splitInputs) {
    const splitViews =
      encoding === "folders"
        ? framesSplitLayout(split.name, split.files, findings)
        : splitLayout(split.name, split.files, task, findings);
    if (splitViews === null) {
      return result([], [], 0, kept.length, ignoredFiles, findings, encoding);
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
      return result([], [], 0, kept.length, ignoredFiles, findings, encoding);
    }
    for (const [name, view] of splitViews.views) {
      const total = viewTotals.get(name) ?? { kind: view.kind, fileCount: 0, groupCount: 0 };
      total.fileCount += view.fileCount;
      total.groupCount = (total.groupCount ?? 0) + (view.groupCount ?? 0);
      viewTotals.set(name, total);
    }
    splits.push({ name: split.name, recordCount: splitViews.recordCount });
  }

  const views: LayoutView[] = [...viewTotals.entries()].map(([name, view]) => ({
    name,
    kind: view.kind,
    fileCount: view.fileCount,
    ...(encoding === "folders" ? { groupCount: view.groupCount ?? 0 } : {}),
  }));

  if (task === "image_text_entity_linking") {
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
  return result(views, splits, totalRecords, kept.length, ignoredFiles, findings, encoding);
}

/** One view's tally within a split (or aggregated across splits). */
interface SplitView {
  kind: MediaFileKind;
  fileCount: number;
  groupCount?: number;
}

/**
 * The video task's source encoding: "files" (video files), "folders" (only
 * frame images), or null when the selection mixes both — a blocking error.
 * Always "files" for the other tasks.
 */
function detectVideoEncoding(
  entries: readonly { relPath: string }[],
  task: RawTask,
): RawVideoEncoding | null {
  if (task !== "video") return "files";
  let videos = 0;
  let images = 0;
  for (const entry of entries) {
    const segments = entry.relPath.split("/").filter(Boolean);
    if (!segments.length || segments.some((segment) => segment.startsWith("."))) continue;
    const kind = classifyMediaName(segments[segments.length - 1]);
    if (kind === "video") videos += 1;
    else if (kind === "image") images += 1;
  }
  if (videos > 0 && images > 0) return null;
  return images > 0 ? "folders" : "files";
}

/** One split's views + record count, or null on a blocking ambiguity. */
function splitLayout(
  splitName: string,
  files: KeptFile[],
  task: RawTask,
  findings: LayoutFinding[],
): { views: Map<string, SplitView>; recordCount: number } | null {
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
    const kind = soleKind(direct, where, task, findings);
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
    const kind = soleKind(dirFiles, `'${dir}/'`, task, findings);
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

/**
 * A frame-folders split: video/frame*.jpg (single view) or view/video/frame*.jpg.
 * Mirrors the backend's `_frames_split_views` exactly.
 */
function framesSplitLayout(
  splitName: string,
  files: KeptFile[],
  findings: LayoutFinding[],
): { views: Map<string, SplitView>; recordCount: number } | null {
  const where = splitName === "default" ? "the folder" : `'${splitName}/'`;
  const depths = [...new Set(files.map((file) => file.segments.length))].sort();
  if (depths.includes(1)) {
    findings.push({
      code: "frames_folder_required",
      severity: "error",
      message:
        `Frame images sit directly in ${where}; put each video's frames in its own folder ` +
        "(video_name/frame.jpg, or view_name/video_name/frame.jpg for several views).",
    });
    return null;
  }
  if (!(depths.length === 1 && (depths[0] === 2 || depths[0] === 3))) {
    findings.push({
      code: "frames_depth_mismatch",
      severity: "error",
      message:
        `${where} must use ONE shape: video folders directly (single view) or one extra ` +
        "view-folder level (several views) — not a mixture or deeper nesting.",
    });
    return null;
  }

  if (depths[0] === 2) {
    const frameNames = new Map<string, string[]>();
    for (const file of files) {
      frameNames.set(file.segments[0], [
        ...(frameNames.get(file.segments[0]) ?? []),
        file.segments[1],
      ]);
    }
    warnLexicographicOrder(frameNames, findings);
    return {
      views: new Map([
        ["video", { kind: "image", fileCount: files.length, groupCount: frameNames.size }],
      ]),
      recordCount: frameNames.size,
    };
  }

  // Depth 3: top-level folders are views, second-level folders are videos.
  const byView = new Map<string, KeptFile[]>();
  for (const file of files) {
    byView.set(file.segments[0], [...(byView.get(file.segments[0]) ?? []), file]);
  }
  const views = new Map<string, SplitView>();
  const videosByView = new Map<string, Set<string>>();
  const namedDirs = new Map<string, string>();
  const frameNames = new Map<string, string[]>();
  for (const [dir, dirFiles] of [...byView.entries()].sort(([a], [b]) => a.localeCompare(b))) {
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
    const videos = new Set(dirFiles.map((file) => file.segments[1]));
    for (const file of dirFiles) {
      const key = `${dir}/${file.segments[1]}`;
      frameNames.set(key, [...(frameNames.get(key) ?? []), file.segments[2]]);
    }
    views.set(name, { kind: "image", fileCount: dirFiles.length, groupCount: videos.size });
    videosByView.set(name, videos);
    namedDirs.set(name, dir);
  }
  warnLexicographicOrder(frameNames, findings);

  const allVideos = new Set<string>();
  for (const videos of videosByView.values()) for (const video of videos) allVideos.add(video);
  let missing = 0;
  for (const videos of videosByView.values()) missing += allVideos.size - videos.size;
  if (missing > 0) {
    findings.push({
      code: "missing_view_file",
      severity: "warning",
      message:
        `${missing} video${missing === 1 ? " is" : "s are"} missing in one of the views ` +
        "(matched by folder name); those views are omitted for those videos.",
    });
  }
  return { views, recordCount: allVideos.size };
}

/** Warn ONCE when unpadded numeric frame names will not sort in numeric order. */
function warnLexicographicOrder(
  frameNames: Map<string, string[]>,
  findings: LayoutFinding[],
): void {
  for (const [folder, names] of frameNames) {
    const plain = [...names].sort();
    const numeric = [...names].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    const divergence = plain.findIndex((name, index) => name !== numeric[index]);
    if (divergence !== -1) {
      findings.push({
        code: "frame_order_lexicographic",
        severity: "warning",
        message:
          `In '${folder}/', '${plain[divergence]}' sorts before '${numeric[divergence]}' — frames ` +
          "import in plain alphabetical order; zero-pad frame numbers if that is not the intent.",
      });
      return;
    }
  }
}

function soleKind(
  files: KeptFile[],
  where: string,
  task: RawTask,
  findings: LayoutFinding[],
): MediaFileKind | null {
  const kinds = [...new Set(files.map((file) => file.kind))].sort();
  if (kinds.length === 1) return kinds[0];
  const hint =
    task === "image_text_entity_linking"
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
  encoding: RawVideoEncoding,
): LayoutPreflight {
  return {
    views,
    splits,
    totalRecords,
    keptFiles,
    ignoredFiles,
    findings,
    ok: !findings.some((finding) => finding.severity === "error"),
    encoding,
  };
}
