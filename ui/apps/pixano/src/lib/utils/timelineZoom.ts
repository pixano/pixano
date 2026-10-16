/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const TIMELINE_ZOOM_MIN = 100;
const TIMELINE_ZOOM_STEP_FACTOR = 1.25;

/** Upper bound of the timeline zoom (percent) for a clip whose last frame index is `lastFrame`. */
export function timelineZoomMax(lastFrame: number | undefined): number {
  return Math.max((lastFrame ?? 0) * 3, 200);
}

/** The zoom (percent) one step in `direction` from `current`, clamped to the slider range. */
export function nextTimelineZoom(current: number, direction: 1 | -1, max: number): number {
  const next =
    direction > 0 ? current * TIMELINE_ZOOM_STEP_FACTOR : current / TIMELINE_ZOOM_STEP_FACTOR;
  return Math.round(Math.min(max, Math.max(TIMELINE_ZOOM_MIN, next)));
}
