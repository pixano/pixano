/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What each entity row of the timeline draws: the entity's own tracklets (never its
 * sub-entities'), one lane per camera plus the merged lane of the collapsed row. Keyframes are
 * cached per children array and models per entity, so a display-only commit rebuilds nothing.
 */

import { hasFrame } from "./laneQueries";
import type { EntityTrackModel, LaneGeom, Span, TrackGeom, TrackInput } from "./types";

type TrackChildren = TrackInput["ui"]["childs"];

/** The largest frame an Int32Array holds; a larger index would wrap to a negative one. */
const MAX_FRAME = 0x7fffffff;

const EMPTY_FRAMES: Int32Array = Object.freeze(new Int32Array(0));

const collator = new Intl.Collator("en", { numeric: true });

/** Keyframes per children array, valid while the array keeps its length. */
const framesCache = new WeakMap<object, { readonly length: number; readonly frames: Int32Array }>();

/** The tracks, in input order, that each model was last matched against. */
const matchedTracks = new WeakMap<EntityTrackModel, readonly TrackGeom[]>();

function compareViewNames(a: string, b: string): number {
  return collator.compare(a, b) || (a < b ? -1 : a > b ? 1 : 0);
}

/** View names in natural order ("cam2" before "cam10"), without duplicates. */
export function sortViewNames(names: Iterable<string>): string[] {
  return [...new Set(names)].sort(compareViewNames);
}

function isFrameIndex(value: number | undefined): boolean {
  return Number.isInteger(value) && value >= 0 && value <= MAX_FRAME;
}

function sortedFramesOf(childs: TrackChildren): Int32Array {
  const distinct = new Set<number>();
  for (const child of childs) {
    const frame = child.ui.frame_index;
    if (isFrameIndex(frame)) distinct.add(frame);
  }
  return Int32Array.from(distinct).sort();
}

function framesOf(childs: TrackChildren): Int32Array {
  const frames = new Int32Array(childs.length);
  let count = 0;
  for (const child of childs) {
    const frame = child.ui.frame_index;
    if (!isFrameIndex(frame)) continue;
    if (count === 0 || frame > frames[count - 1]) frames[count++] = frame;
    else if (frame < frames[count - 1]) return sortedFramesOf(childs);
  }
  if (count === 0) return EMPTY_FRAMES;
  return count === frames.length ? frames : frames.slice(0, count);
}

/**
 * The distinct integer `frame_index` values >= 0 of a tracklet's children, ascending. Cached
 * per array: the same array, at the same length, gives back the same Int32Array.
 */
export function distinctSortedFrames(childs: TrackChildren | undefined): Int32Array {
  if (!childs || childs.length === 0) return EMPTY_FRAMES;
  const cached = framesCache.get(childs);
  if (cached && cached.length === childs.length) return cached.frames;
  const frames = framesOf(childs);
  framesCache.set(childs, { length: childs.length, frames });
  return frames;
}

/** One tracklet as the timeline draws it: its range (start <= end), color and keyframes. */
export function buildTrackGeom(track: TrackInput, color: string): TrackGeom {
  const data = track.data;
  return {
    id: track.id,
    view: data.view_name,
    start: Math.min(data.start_frame, data.end_frame),
    end: Math.max(data.start_frame, data.end_frame),
    color,
    frames: distinctSortedFrames(track.ui.childs),
  };
}

/** The lane of an entity without tracks: shared and frozen. */
export const EMPTY_LANE: LaneGeom = Object.freeze({
  view: null,
  tracks: Object.freeze<TrackGeom[]>([]),
  spans: Object.freeze<Span[]>([]),
  frames: EMPTY_FRAMES,
  capFrames: EMPTY_FRAMES,
});

function compareTracks(a: TrackGeom, b: TrackGeom): number {
  return a.start - b.start || a.end - b.end || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

/** Drops the repeats of a sorted list, in place; copies only when it shrinks. */
function dedupeSorted(values: Int32Array): Int32Array {
  let count = 0;
  for (let index = 0; index < values.length; index++) {
    if (count === 0 || values[index] !== values[count - 1]) values[count++] = values[index];
  }
  return count === values.length ? values : values.slice(0, count);
}

/** The distinct union of sorted keyframe lists; a lone non-empty list comes back as is. */
function unionFrames(lists: readonly Int32Array[]): Int32Array {
  let total = 0;
  let filled = 0;
  let only = EMPTY_FRAMES;
  for (const list of lists) {
    if (list.length === 0) continue;
    total += list.length;
    filled++;
    only = list;
  }
  if (filled <= 1) return only;
  const merged = new Int32Array(total);
  let offset = 0;
  let sorted = true;
  for (const list of lists) {
    if (list.length === 0) continue;
    if (offset > 0 && list[0] < merged[offset - 1]) sorted = false;
    merged.set(list, offset);
    offset += list.length;
  }
  if (!sorted) merged.sort();
  return dedupeSorted(merged);
}

/** The keyframes that start or end their own track. */
function ownBoundaryCaps(tracks: readonly TrackGeom[]): Int32Array {
  const caps: number[] = [];
  for (const track of tracks) {
    if (hasFrame(track.frames, track.start)) caps.push(track.start);
    if (track.end !== track.start && hasFrame(track.frames, track.end)) caps.push(track.end);
  }
  return caps.length === 0 ? EMPTY_FRAMES : dedupeSorted(Int32Array.from(caps).sort());
}

/** The tracks' ranges by start then end, merged where they overlap or touch, in the first color. */
function mergedSpans(tracks: readonly TrackGeom[]): Span[] {
  const ordered = tracks.slice().sort((a, b) => a.start - b.start || a.end - b.end);
  const spans: { start: number; end: number; color: string }[] = [];
  for (const track of ordered) {
    const last = spans[spans.length - 1];
    if (last && track.start <= last.end + 1) last.end = Math.max(last.end, track.end);
    else spans.push({ start: track.start, end: track.end, color: track.color });
  }
  return spans;
}

/** The keyframes on a span's start or end, in one walk over both sorted lists. */
function spanBoundaryCaps(frames: Int32Array, spans: readonly Span[]): Int32Array {
  const caps: number[] = [];
  let index = 0;
  const visit = (boundary: number) => {
    while (index < frames.length && frames[index] < boundary) index++;
    if (frames[index] === boundary && caps[caps.length - 1] !== boundary) caps.push(boundary);
  };
  for (const span of spans) {
    visit(span.start);
    visit(span.end);
  }
  return caps.length === 0 ? EMPTY_FRAMES : Int32Array.from(caps);
}

/**
 * One camera's lane: its tracks by start, end and id, one presence line per track (a split
 * stays two lines), caps on the keyframes that start or end their own track.
 */
export function buildViewLane(view: string, tracks: readonly TrackGeom[]): LaneGeom {
  const ordered = tracks.slice().sort(compareTracks);
  return {
    view,
    tracks: ordered,
    spans: ordered.map(({ start, end, color }) => ({ start, end, color })),
    frames: unionFrames(ordered.map((track) => track.frames)),
    capFrames: ownBoundaryCaps(ordered),
  };
}

/**
 * The merged lane of an entity seen by several cameras, from its tracks in view rank order:
 * presence lines merged where they overlap or touch, caps only on a merged line's ends.
 */
export function buildUnionLane(tracks: readonly TrackGeom[]): LaneGeom {
  if (tracks.length === 0) return EMPTY_LANE;
  const frames = unionFrames(tracks.map((track) => track.frames));
  const spans = mergedSpans(tracks);
  return {
    view: null,
    tracks: tracks.slice(),
    spans,
    frames,
    capFrames: spanBoundaryCaps(frames, spans),
  };
}

/** View rank: the views of `viewOrder` by index, then the others in natural order. */
function viewComparator(viewOrder: readonly string[]): (a: string, b: string) => number {
  const rank = new Map<string, number>();
  viewOrder.forEach((view, index) => {
    if (!rank.has(view)) rank.set(view, index);
  });
  return (a, b) => {
    const rankA = rank.get(a);
    const rankB = rank.get(b);
    if (rankA === undefined) return rankB === undefined ? compareViewNames(a, b) : 1;
    return rankB === undefined ? -1 : rankA - rankB;
  };
}

function entityModel(
  entityId: string,
  tracks: readonly TrackGeom[],
  compareViews: (a: string, b: string) => number,
): EntityTrackModel {
  const groups = new Map<string, TrackGeom[]>();
  let firstFrame = Infinity;
  for (const track of tracks) {
    const group = groups.get(track.view);
    if (group) group.push(track);
    else groups.set(track.view, [track]);
    if (track.start < firstFrame) firstFrame = track.start;
  }
  const byView = new Map<string, LaneGeom>();
  for (const view of [...groups.keys()].sort(compareViews)) {
    byView.set(view, buildViewLane(view, groups.get(view)));
  }
  const lanes = [...byView.values()];
  let union = EMPTY_LANE;
  if (lanes.length === 1) union = lanes[0];
  else if (lanes.length > 1) union = buildUnionLane(lanes.flatMap((lane) => lane.tracks));
  return { entityId, firstFrame, union, byView };
}

/**
 * An entity's model from its own tracklets: a lane per camera in view rank order, and the
 * union, which is that lane itself when a single camera sees the entity.
 */
export function buildEntityTrackModel<T extends TrackInput>(
  entityId: string,
  tracks: readonly T[],
  viewOrder: readonly string[],
  colorOf: (track: T) => string,
): EntityTrackModel {
  const geoms = tracks.map((track) => buildTrackGeom(track, colorOf(track)));
  return entityModel(entityId, geoms, viewComparator(viewOrder));
}

/** The track models of a record, kept from one build to the next. */
export interface TrackModelCache {
  /** The view order the models were built for, joined with "\u0001". */
  readonly viewKey: string;
  /** One model per entity with an own tracklet, by entity id. */
  readonly models: ReadonlyMap<string, EntityTrackModel>;
}

function sameFrames(a: Int32Array, b: Int32Array): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let index = 0; index < a.length; index++) if (a[index] !== b[index]) return false;
  return true;
}

function sameTracks(a: readonly TrackGeom[], b: readonly TrackGeom[]): boolean {
  if (a.length !== b.length) return false;
  for (let index = 0; index < a.length; index++) {
    const x = a[index];
    const y = b[index];
    if (x.id !== y.id || x.view !== y.view || x.start !== y.start || x.end !== y.end) return false;
    if (x.color !== y.color || !sameFrames(x.frames, y.frames)) return false;
  }
  return true;
}

/**
 * The model of every entity with an own tracklet, grouped by `data.entity_id` in order of first
 * appearance. An entity whose tracks are unchanged keeps its previous model, and `previous`
 * itself comes back when nothing changed; a hit costs O(tracks), never O(children).
 */
export function buildTrackModels<T extends TrackInput>(
  tracklets: readonly T[],
  viewOrder: readonly string[],
  colorOf: (track: T) => string,
  previous: TrackModelCache | null,
): TrackModelCache {
  const viewKey = viewOrder.join("\u0001");
  const reusable = previous?.viewKey === viewKey ? previous.models : null;
  const groups = new Map<string, TrackGeom[]>();
  for (const tracklet of tracklets) {
    const entityId = tracklet.data.entity_id;
    if (!entityId) continue;
    const geom = buildTrackGeom(tracklet, colorOf(tracklet));
    const group = groups.get(entityId);
    if (group) group.push(geom);
    else groups.set(entityId, [geom]);
  }
  const compareViews = viewComparator(viewOrder);
  const models = new Map<string, EntityTrackModel>();
  let unchanged = reusable !== null && reusable.size === groups.size;
  for (const [entityId, tracks] of groups) {
    let model = reusable?.get(entityId);
    const matched = model ? matchedTracks.get(model) : undefined;
    if (!matched || !sameTracks(matched, tracks)) {
      model = entityModel(entityId, tracks, compareViews);
      unchanged = false;
    }
    // Frames equal by value now compare by identity on the next build.
    matchedTracks.set(model, tracks);
    models.set(entityId, model);
  }
  return unchanged ? previous : { viewKey, models };
}
