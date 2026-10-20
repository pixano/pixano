/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SequenceFrame } from "$lib/types/dataset";
import {
  buildFrameLocator,
  isFrameLocator,
  type FrameLocator,
  type ViewLocator,
  type WorkspaceLocator,
} from "$lib/types/workspaceLocators";

export function resolveSequenceFrameLocator(
  logicalName: string,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
  fallback: WorkspaceLocator,
): FrameLocator {
  if (!viewFrames || !Number.isFinite(frameIndex) || frameIndex < 0) {
    return isFrameLocator(fallback)
      ? fallback
      : {
          frameId: fallback.id,
          logicalName: fallback.logicalName,
          frameIndex,
        };
  }

  const frame =
    viewFrames.find((candidate) => candidate.data.frame_index === frameIndex) ??
    viewFrames[frameIndex];
  if (!frame) {
    return isFrameLocator(fallback)
      ? fallback
      : {
          frameId: fallback.id,
          logicalName: fallback.logicalName,
          frameIndex,
        };
  }

  return buildFrameLocator(frame, logicalName);
}

export function resolveVideoFrameIdentity(
  viewLocator: ViewLocator | FrameLocator,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
): { frameLocator: FrameLocator; frameIndex: number } {
  return {
    frameLocator: resolveSequenceFrameLocator(
      viewLocator.logicalName,
      frameIndex,
      viewFrames,
      viewLocator,
    ),
    frameIndex,
  };
}

type IndexedFrame = { data: { frame_index: number } };

/**
 * The frame of a view whose frame_index is `frameIndex`, or undefined. Never the array
 * position: a view can miss frames or start after frame 0.
 */
export function findSequenceFrameByIndex<T extends IndexedFrame>(
  frames: ReadonlyArray<T> | undefined,
  frameIndex: number,
): T | undefined {
  if (!frames || !Number.isInteger(frameIndex)) return undefined;
  // Views are sorted by frame_index on load: try the position it would have first.
  const guess = frames[frameIndex];
  if (guess?.data.frame_index === frameIndex) return guess;
  let low = 0;
  let high = frames.length - 1;
  while (low <= high) {
    const mid = (low + high) >>> 1;
    const value = frames[mid].data.frame_index;
    if (value === frameIndex) return frames[mid];
    if (value < frameIndex) low = mid + 1;
    else high = mid - 1;
  }
  return frames.find((frame) => frame.data.frame_index === frameIndex);
}

/** The frame_index range of a view's frames, clamped to `[0, lastFrame]`; null when empty. */
export function sequenceFrameRange(
  frames: ReadonlyArray<IndexedFrame> | undefined,
  lastFrame?: number,
): { first: number; last: number } | null {
  if (!frames || frames.length === 0) return null;
  let first = Number.POSITIVE_INFINITY;
  let last = Number.NEGATIVE_INFINITY;
  for (const frame of frames) {
    first = Math.min(first, frame.data.frame_index);
    last = Math.max(last, frame.data.frame_index);
  }
  first = Math.max(0, first);
  if (lastFrame !== undefined && Number.isFinite(lastFrame)) last = Math.min(last, lastFrame);
  return first <= last ? { first, last } : null;
}
