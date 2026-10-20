/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Shapes shared by the video timeline's pure modules (`lib/timeline`). Plain data only:
 * these modules run under vitest in node, without the Svelte runtime, and the stores and
 * components feed them what they read from the workspace.
 */

// ─── Geometry ───────────────────────────────────────────────────────────────

/**
 * The one frame↔x mapping of the timeline lanes, in lane pixels (0 is the lane's left
 * edge). The ruler, the tracks, the playhead and every pointer hit test use it.
 */
export interface TimelineGeometry {
  /** The last frame index, at least 0. */
  readonly lastFrame: number;
  /** The lane's full width, in px. */
  readonly laneWidth: number;
  /** Inner padding on both sides, so the marks on frame 0 and on the last frame show whole. */
  readonly padX: number;
  /** `laneWidth − 2·padX`, at least 1. */
  readonly innerWidth: number;
  /** `innerWidth / max(lastFrame, 1)`. */
  readonly pxPerFrame: number;
}

/** A horizontal range of a lane, in lane px. */
export interface PxWindow {
  readonly x0: number;
  readonly x1: number;
}

/** An inclusive range of integer frames. */
export interface FrameWindow {
  readonly first: number;
  readonly last: number;
}

// ─── Track model ────────────────────────────────────────────────────────────

/** What the track model reads from a tracklet (structural, so tests can pass plain objects). */
export interface TrackInput {
  readonly id: string;
  readonly data: {
    readonly entity_id?: string;
    readonly view_name: string;
    readonly start_frame: number;
    readonly end_frame: number;
  };
  readonly ui: {
    readonly childs?: ReadonlyArray<{ readonly ui: { readonly frame_index?: number } }>;
  };
}

/** One tracklet as the timeline draws it. */
export interface TrackGeom {
  readonly id: string;
  readonly view: string;
  /** min(start_frame, end_frame). */
  readonly start: number;
  /** max(start_frame, end_frame). */
  readonly end: number;
  readonly color: string;
  /** The distinct frames the tracklet has a stored child on (its keyframes), ascending. */
  readonly frames: Int32Array;
}

/** A presence line: the frames from `start` to `end` (inclusive) are covered. */
export interface Span {
  readonly start: number;
  readonly end: number;
  readonly color: string;
}

/**
 * What one timeline lane shows: one camera's tracks of an entity (`view` set), or every
 * camera's tracks merged (`view` null, the union row of a multi-view record).
 */
export interface LaneGeom {
  readonly view: string | null;
  /** The lane's tracks, by view rank, then start, end and id. */
  readonly tracks: readonly TrackGeom[];
  /** Presence lines, ascending by start: one per track in a camera lane, merged in a union lane. */
  readonly spans: readonly Span[];
  /** Distinct keyframes of every track of the lane, ascending. */
  readonly frames: Int32Array;
  /** The keyframes drawn as the taller start/end caps, ascending; a subset of `frames`. */
  readonly capFrames: Int32Array;
}

/** An entity's own tracks (never its sub-entities'), per camera and merged. */
export interface EntityTrackModel {
  readonly entityId: string;
  /** The first frame any of its tracks covers (Infinity without tracks). */
  readonly firstFrame: number;
  /** The collapsed row: the one camera's lane when a single camera sees the entity. */
  readonly union: LaneGeom;
  /** One lane per camera with a track, in view rank order. */
  readonly byView: ReadonlyMap<string, LaneGeom>;
}

// ─── Marks ──────────────────────────────────────────────────────────────────

/** A vertical bar of a lane mark: top `y`, height `h` and width `w`, in px. */
export interface MarkBox {
  readonly y: number;
  readonly h: number;
  readonly w: number;
}

/** Where a lane draws its marks; all values in px from the top of the lane. */
export interface MarkGeometry {
  /** Lane height. */
  readonly rowHeight: number;
  /** Presence line (its `w` is unused). */
  readonly line: MarkBox;
  readonly tick: MarkBox;
  /** Start/end keyframe of a track (or of a merged presence span). */
  readonly cap: MarkBox;
  /** The selected keyframe. */
  readonly selected: MarkBox;
  readonly hoverTick: MarkBox;
  readonly hoverCap: MarkBox;
}

/** Entity rows (36 px lanes), from the design canvas's `geoBig`. */
export const MARKS_ENTITY: MarkGeometry = {
  rowHeight: 36,
  line: { y: 17, h: 2, w: 0 },
  tick: { y: 12, h: 12, w: 2 },
  cap: { y: 9, h: 18, w: 3 },
  selected: { y: 7, h: 22, w: 4 },
  hoverTick: { y: 11, h: 14, w: 3 },
  hoverCap: { y: 8, h: 20, w: 4 },
};
