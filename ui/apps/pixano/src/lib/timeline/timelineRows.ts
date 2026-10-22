/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Which rows the video timeline lists, in which order, and which one is selected. Rows are
 * ranked once per record visit and the ranks stay frozen, so a row never jumps after an
 * edit: rows that appear later go last.
 */

import { formatFps } from "./timeFormat";

// ─── Order ──────────────────────────────────────────────────────────────────

/** What a row is ranked by. */
export interface RankKey {
  readonly id: string;
  /** The first frame of the entity's own tracks (Infinity without tracks). */
  readonly firstFrame: number;
  /** The display name; null (or empty) when the entity has none. */
  readonly name: string | null;
  /** The parent entity's id; null or "" for a top-level entity. */
  readonly parentId: string | null;
}

const NATURAL = new Intl.Collator("en", { numeric: true });

// Natural order ("obj2" before "obj10"), then code units, so distinct ids never tie.
function compareIds(a: string, b: string): number {
  return NATURAL.compare(a, b) || (a < b ? -1 : a > b ? 1 : 0);
}

// A first frame that is not a number sorts like a row without tracks.
function frameKey(frame: number): number {
  return typeof frame === "number" && !Number.isNaN(frame) ? frame : Infinity;
}

// Rows of one level: first frame (rows without tracks last), then name (unnamed last), then id.
function compareRankKeys(a: RankKey, b: RankKey): number {
  const frameA = frameKey(a.firstFrame);
  const frameB = frameKey(b.firstFrame);
  if (frameA !== frameB) return frameA < frameB ? -1 : 1;
  if (a.name && b.name) {
    const byName = NATURAL.compare(a.name, b.name);
    if (byName !== 0) return byName;
  } else if (a.name || b.name) {
    return a.name ? -1 : 1;
  }
  return compareIds(a.id, b.id);
}

/**
 * Ranks from 0: top-level rows (no parent, or a parent without a row) by first frame, name
 * and id, each followed by its sub-entities, ranked the same way, and theirs in turn.
 */
export function rankTimelineRows(keys: readonly RankKey[]): Map<string, number> {
  const byId = new Map<string, RankKey>();
  for (const key of keys) if (!byId.has(key.id)) byId.set(key.id, key);
  const roots: RankKey[] = [];
  const childrenOf = new Map<string, RankKey[]>();
  for (const key of byId.values()) {
    const { parentId } = key;
    if (!parentId || parentId === key.id || !byId.has(parentId)) {
      roots.push(key);
      continue;
    }
    const children = childrenOf.get(parentId);
    if (children) children.push(key);
    else childrenOf.set(parentId, [key]);
  }
  const ranks = new Map<string, number>();
  const visit = (key: RankKey): void => {
    if (ranks.has(key.id)) return;
    ranks.set(key.id, ranks.size);
    for (const child of childrenOf.get(key.id)?.sort(compareRankKeys) ?? []) visit(child);
  };
  roots.sort(compareRankKeys).forEach(visit);
  // A parent chain that loops reaches no top-level row: the loop's first key stands for one,
  // so the sub-entities hanging off the loop still follow their parent.
  if (ranks.size < byId.size) {
    [...byId.values()]
      .filter((key) => !ranks.has(key.id) && isOnParentLoop(key, byId))
      .sort(compareRankKeys)
      .forEach(visit);
  }
  return ranks;
}

// Whether following the parents of `key` leads back to it.
function isOnParentLoop(key: RankKey, byId: ReadonlyMap<string, RankKey>): boolean {
  const seen = new Set<string>();
  let parent = byId.get(key.parentId);
  while (parent && !seen.has(parent.id)) {
    if (parent.id === key.id) return true;
    seen.add(parent.id);
    parent = byId.get(parent.parentId);
  }
  return false;
}

/**
 * `ranks` plus the ids of `keys` it lacks, ranked after its highest rank in the order
 * `rankTimelineRows` gives them among themselves; `ranks` itself when no id is new.
 */
export function extendTimelineRanks(
  ranks: ReadonlyMap<string, number>,
  keys: readonly RankKey[],
): ReadonlyMap<string, number> {
  const fresh = keys.filter((key) => !ranks.has(key.id));
  if (fresh.length === 0) return ranks;
  let last = -1;
  for (const rank of ranks.values()) last = Math.max(last, rank);
  const extended = new Map(ranks);
  for (const [id, rank] of rankTimelineRows(fresh)) extended.set(id, last + 1 + rank);
  return extended;
}

// ─── Rows ───────────────────────────────────────────────────────────────────

/** The candidates in rank order; ids without a rank last, by id. */
export function orderTimelineRows(
  candidateIds: Iterable<string>,
  ranks: ReadonlyMap<string, number>,
): string[] {
  const rankOf = (id: string) => ranks.get(id) ?? Infinity;
  return [...new Set(candidateIds)].sort((a, b) => {
    const rankA = rankOf(a);
    const rankB = rankOf(b);
    return rankA !== rankB ? (rankA < rankB ? -1 : 1) : compareIds(a, b);
  });
}

/** Whether two row lists list the same rows in the same order, so the store keeps the old one. */
export function sameTimelineRows(a: readonly string[] | null, b: readonly string[]): boolean {
  return (
    a === b || (a !== null && a.length === b.length && a.every((id, index) => id === b[index]))
  );
}

// ─── Selection ──────────────────────────────────────────────────────────────

/** What the selected row depends on. */
export interface SelectedRowInput {
  /** The selected (highlighted) top-level entity. */
  readonly selectedTopId: string | null;
  /** The row last activated on the timeline. */
  readonly focusedRowId: string | null;
  /** The entity that owns the track in edit mode. */
  readonly editedTrackOwnerId: string | null;
  /** The top-level entity of an entity: itself for a top-level entity. */
  readonly topIdOf: (entityId: string) => string | null | undefined;
}

/**
 * The selected row: the focused row, else the edited track's own entity, when it belongs to
 * the selected top-level entity; else that entity. Clicking a sub-entity's row selects its
 * top-level entity in the canvas, while the timeline keeps the clicked row selected.
 */
export function resolveSelectedRow({
  selectedTopId,
  focusedRowId,
  editedTrackOwnerId,
  topIdOf,
}: SelectedRowInput): string | null {
  if (!selectedTopId) return null;
  if (focusedRowId && topIdOf(focusedRowId) === selectedTopId) return focusedRowId;
  if (editedTrackOwnerId && topIdOf(editedTrackOwnerId) === selectedTopId) {
    return editedTrackOwnerId;
  }
  return selectedTopId;
}

/** What `storedSelfEntityId` reads of a tracklet. */
export interface HighlightedTrack {
  readonly data: { readonly entity_id?: string };
  readonly ui: {
    readonly displayControl: { readonly highlighted?: string };
    readonly top_entities?: ReadonlyArray<{ readonly id: string }>;
  };
}

/**
 * The top-level entity of the first tracklet highlighted as "self", or null: the selection
 * stored on the annotations under tools other than Pan (Fusion, right after a save).
 */
export function storedSelfEntityId(tracks: Iterable<HighlightedTrack>): string | null {
  for (const track of tracks) {
    if (track.ui.displayControl.highlighted !== "self") continue;
    const topId = track.ui.top_entities?.[0]?.id ?? track.data.entity_id;
    if (topId) return topId;
  }
  return null;
}

// ─── Row display ────────────────────────────────────────────────────────────

/** What the row rules read of an annotation's display state. */
export interface DisplayedChild {
  readonly ui: {
    readonly displayControl: { readonly hidden?: boolean; readonly highlighted?: string };
  };
}

/** A highlight state, as annotations store it in `ui.displayControl.highlighted`. */
export type RowHighlightState = "all" | "self" | "none";

/** An entity's Fusion highlight: "self" if a child is "self", else "none" if one is, else "all". */
export function fusionHighlightState(
  childs: ReadonlyArray<DisplayedChild> | null | undefined,
): RowHighlightState {
  let state: RowHighlightState = "all";
  for (const child of childs ?? []) {
    const { highlighted } = child.ui.displayControl;
    if (highlighted === "self") return "self";
    if (highlighted === "none") state = "none";
  }
  return state;
}

/** Whether the inspector shows an entity as hidden: it has children, all of them hidden. */
export function isHiddenInInspector(
  childs: ReadonlyArray<DisplayedChild> | null | undefined,
): boolean {
  if (!childs || childs.length === 0) return false;
  return childs.every((child) => child.ui.displayControl.hidden === true);
}

/** The opacity of a row's graphics; its text never dims, to keep its contrast. */
export function rowGraphicsOpacity({
  hiddenInInspector,
  fusionDimmed,
}: {
  readonly hiddenInInspector: boolean;
  readonly fusionDimmed: boolean;
}): number {
  if (hiddenInInspector) return 0.5;
  return fusionDimmed ? 0.4 : 1;
}

/** A row's keyframe count, as its header shows it ("12 kf"). */
export function rowKeyframeLabel(count: number): string {
  return `${count} kf`;
}

// ─── Empty states and corner ────────────────────────────────────────────────

/** Why the timeline lists no entity row. */
export type TimelineEmptyState = "no-tracks" | "all-hidden";

/** The text of each empty state. */
export const TIMELINE_EMPTY_TEXT: Readonly<Record<TimelineEmptyState, string>> = {
  "no-tracks": "No tracked objects in this record yet.",
  "all-hidden": "All tracks are hidden. Show them from the Entities tab.",
};

/** The empty state: nothing tracked, or every tracked entity hidden; null when rows show. */
export function timelineEmptyState({
  trackedCount,
  visibleCount,
}: {
  readonly trackedCount: number;
  readonly visibleCount: number;
}): TimelineEmptyState | null {
  if (!(trackedCount > 0)) return "no-tracks";
  return visibleCount > 0 ? null : "all-hidden";
}

/** The texts of the ruler's corner. */
export interface CornerLabel {
  /** "29.97 fps"; null when the frame rate is unknown. */
  readonly fps: string | null;
  /** "1 frame", "200 frames". */
  readonly frames: string;
}

/** The ruler corner's frame rate and frame count. */
export function cornerLabel(fps: number | null, frameCount: number): CornerLabel {
  return {
    fps: fps > 0 && Number.isFinite(fps) ? `${formatFps(fps)} fps` : null,
    frames: frameCount === 1 ? "1 frame" : `${frameCount} frames`,
  };
}
