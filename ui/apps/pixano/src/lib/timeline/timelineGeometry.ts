/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The timeline's one frame↔x mapping. The ruler, the tracks, the playhead and every
 * pointer hit test go through it, so a frame sits at the same x everywhere: frame 0 at
 * the lane's inner left edge, the last frame at its inner right edge. Also the horizontal
 * render window, the snapping of marks to device pixels, and the scroll positions of a
 * zoom or a reveal, all in lane px.
 */

import type { FrameWindow, PxWindow, TimelineGeometry } from "./types";

/** Width of the sticky column of row headers, in px. */
export const TIMELINE_HEADER_WIDTH = 236;
/** Inner padding of a lane on both sides, so the marks on its first and last frames show whole. */
export const TIMELINE_LANE_PAD_X = 12;

/** The lane width for a zoom (percent of the visible lane width); never narrower than the view. */
export function laneWidthForZoom(viewportWidth: number, zoomPercent: number): number {
  const width = Math.max(0, viewportWidth);
  return Math.max(width, Math.round((width * zoomPercent) / 100));
}

/** The mapping of a clip whose last frame is `lastFrame` onto a lane `laneWidth` px wide. */
export function createTimelineGeometry(
  lastFrame: number | undefined,
  laneWidth: number,
  padX: number = TIMELINE_LANE_PAD_X,
): TimelineGeometry {
  const last = Number.isFinite(lastFrame) ? Math.max(0, Math.floor(lastFrame)) : 0;
  const width = Math.max(0, laneWidth);
  const innerWidth = Math.max(1, width - 2 * padX);
  return {
    lastFrame: last,
    laneWidth: width,
    padX,
    innerWidth,
    pxPerFrame: innerWidth / Math.max(last, 1),
  };
}

/** The x of a frame (fractional frames allowed), in lane px. */
export function frameToX(geometry: TimelineGeometry, frame: number): number {
  return geometry.padX + frame * geometry.pxPerFrame;
}

/** The fractional frame under a lane x, unclamped. */
export function xToFrameFloat(geometry: TimelineGeometry, x: number): number {
  return (x - geometry.padX) / geometry.pxPerFrame;
}

/** The nearest frame under a lane x, clamped to the clip. */
export function xToFrame(geometry: TimelineGeometry, x: number): number {
  const frame = Math.round(xToFrameFloat(geometry, x));
  if (!Number.isFinite(frame)) return 0;
  return Math.min(geometry.lastFrame, Math.max(0, frame));
}

/** The scroll distance between two render windows: half a viewport, at least 128 px. */
export function horizontalWindowStep(viewportWidth: number): number {
  return Math.max(128, Number.isFinite(viewportWidth) ? Math.round(viewportWidth / 2) : 0);
}

/** The render window a scroll position falls in; it changes once per window step. */
export function horizontalWindowIndex(scrollLeft: number, viewportWidth: number): number {
  const left = Number.isFinite(scrollLeft) ? Math.max(0, scrollLeft) : 0;
  return Math.floor(left / horizontalWindowStep(viewportWidth));
}

/**
 * The lane range drawn for a render window: two steps before it, two after it plus the
 * viewport. Wherever the scroll sits in the step, that leaves at least a viewport of margin
 * on the left and half a viewport on the right. Kept within the lane.
 */
export function horizontalRenderWindow(
  index: number,
  viewportWidth: number,
  laneWidth: number,
): PxWindow {
  const step = horizontalWindowStep(viewportWidth);
  const viewport = Number.isFinite(viewportWidth) ? Math.max(0, viewportWidth) : 0;
  const width = laneWidth > 0 ? laneWidth : 0;
  const x0 = Math.min(width, Math.max(0, (index - 2) * step));
  return { x0, x1: Math.max(x0, Math.min(width, (index + 2) * step + viewport)) };
}

/** The frames a lane range shows, with one frame of margin on each side, clamped to the clip. */
export function frameWindowOf(geometry: TimelineGeometry, pxWindow: PxWindow): FrameWindow {
  return {
    first: clampFrame(geometry, Math.floor(xToFrameFloat(geometry, pxWindow.x0)) - 1),
    last: clampFrame(geometry, Math.ceil(xToFrameFloat(geometry, pxWindow.x1)) + 1),
  };
}

/** `value` rounded to the device pixel grid; a `dpr` not positive or not finite counts as 1. */
export function snapEdge(value: number, dpr: number): number {
  const ratio = dpr > 0 && Number.isFinite(dpr) ? dpr : 1;
  return Math.round(value * ratio) / ratio;
}

/** The center of a mark `width` px wide at `x`, moved so its left edge sits on the pixel grid. */
export function snapCenter(x: number, width: number, dpr: number): number {
  return snapEdge(x - width / 2, dpr) + width / 2;
}

/** The frame a zoom holds still: the playhead when in view, else the (fractional) center frame. */
export function zoomAnchorFrame(
  geometry: TimelineGeometry,
  scrollLeft: number,
  viewportWidth: number,
  playheadFrame: number,
): number {
  const x = frameToX(geometry, playheadFrame);
  if (x >= scrollLeft && x <= scrollLeft + viewportWidth) return playheadFrame;
  return xToFrameFloat(geometry, scrollLeft + viewportWidth / 2);
}

/** The scroll that keeps `anchorFrame` at the same screen x when zooming from `prev` to `next`. */
export function anchoredScrollLeft(
  prev: TimelineGeometry,
  next: TimelineGeometry,
  scrollLeft: number,
  anchorFrame: number,
  viewportWidth: number,
): number {
  const screenX = frameToX(prev, anchorFrame) - scrollLeft;
  return clampOffset(frameToX(next, anchorFrame) - screenX, next.laneWidth - viewportWidth);
}

/**
 * The scroll position that pages `frame` to a quarter of the viewport; null when it already
 * shows at least `margin` px inside the viewport, or when the clamped position is the current one.
 */
export function revealScrollLeft(
  geometry: TimelineGeometry,
  scrollLeft: number,
  viewportWidth: number,
  frame: number,
  margin = 24,
): number | null {
  const x = frameToX(geometry, frame);
  if (!Number.isFinite(x)) return null;
  if (x >= scrollLeft + margin && x <= scrollLeft + viewportWidth - margin) return null;
  const target = clampOffset(x - viewportWidth / 4, geometry.laneWidth - viewportWidth);
  return target === scrollLeft ? null : target;
}

/** The width of the playhead badge on `frame`: its digits plus 7 px of padding on each side. */
export function badgeWidthForFrame(frame: number, charWidth = 6.6): number {
  return 14 + charWidth * String(Math.round(frame)).length;
}

/** The left edge of the playhead badge: centered on the playhead, kept inside the lane. */
export function playheadBadgeLeft(
  geometry: TimelineGeometry,
  frame: number,
  badgeWidth: number,
): number {
  return clampOffset(frameToX(geometry, frame) - badgeWidth / 2, geometry.laneWidth - badgeWidth);
}

function clampFrame(geometry: TimelineGeometry, frame: number): number {
  return Number.isNaN(frame) ? 0 : Math.min(geometry.lastFrame, Math.max(0, frame));
}

/** `value` clamped to [0, max(0, `max`)]; 0 when it is not a number. */
function clampOffset(value: number, max: number): number {
  return Number.isNaN(value) ? 0 : Math.min(Math.max(0, max), Math.max(0, value));
}
