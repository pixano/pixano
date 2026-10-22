/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What the track menu offers for one of a row's own tracks at the clicked frame. The menu
 * and its actions are built elsewhere; the keyframe rules are those of the canvas chip
 * (`trackFrameActions` in `lib/stores/trackEditing.ts`), on any frame.
 */

import { hasFrame, nextKeyframe, previousKeyframe } from "./laneQueries";

/** One of a row's own tracks, as the track menu reads it. */
export interface MenuTrack {
  readonly id: string;
  readonly view: string;
  readonly start: number;
  readonly end: number;
  /** The distinct frames with any stored child, ascending. */
  readonly keyframes: ArrayLike<number>;
  /** The distinct frames with a box or keypoints child, ascending. */
  readonly editableFrames: ArrayLike<number>;
}

/** Which track menu items apply to a track at a frame. */
export interface TrackMenuAvailability {
  readonly trackletId: string;
  readonly view: string;
  readonly frame: number;
  /** The track has a stored child on the frame. */
  readonly isKeyframe: boolean;
  /** A box or keypoints child on the frame: masks and multi-paths cannot be edited in video. */
  readonly canEdit: boolean;
  /** A keyframe whose removal leaves at least two. */
  readonly canRemove: boolean;
  /** An interpolated frame inside the track, with a box or keypoints on both sides. */
  readonly canAdd: boolean;
  /** Splitting right after the frame leaves a track on each side. */
  readonly canSplit: boolean;
  /** The nearest own track of the same view that ends before this one starts. */
  readonly glueBefore: string | null;
  /** The nearest own track of the same view that starts after this one ends. */
  readonly glueAfter: string | null;
}

/** What the menu offers for `track` at `frame`, among the row's own tracks (any view). */
export function trackMenuAvailability(
  track: MenuTrack,
  ownTracks: ReadonlyArray<Pick<MenuTrack, "id" | "view" | "start" | "end">>,
  frame: number,
): TrackMenuAvailability {
  const { start, end, keyframes, editableFrames } = track;
  const isKeyframe = hasFrame(keyframes, frame);
  let glueBefore: string | null = null;
  let glueAfter: string | null = null;
  let beforeEnd = -Infinity;
  let afterStart = Infinity;
  for (const other of ownTracks) {
    if (other.id === track.id || other.view !== track.view) continue;
    if (other.end < start && other.end > beforeEnd) {
      glueBefore = other.id;
      beforeEnd = other.end;
    }
    if (other.start > end && other.start < afterStart) {
      glueAfter = other.id;
      afterStart = other.start;
    }
  }
  return {
    trackletId: track.id,
    view: track.view,
    frame,
    isKeyframe,
    canEdit: isKeyframe && hasFrame(editableFrames, frame),
    canRemove: isKeyframe && keyframes.length > 2,
    canAdd:
      !isKeyframe &&
      start < frame &&
      frame < end &&
      previousKeyframe(editableFrames, frame) !== null &&
      nextKeyframe(editableFrames, frame) !== null,
    canSplit: start <= frame && frame < end,
    glueBefore,
    glueAfter,
  };
}

/** A track's heading in the menu: `left · #0–#58`. */
export function trackMenuHeading(track: Pick<MenuTrack, "view" | "start" | "end">): string {
  return `${track.view} · #${track.start}–#${track.end}`;
}
