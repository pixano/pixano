/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type PlaybackStep = { action: "stop" } | { action: "seek"; frame: number };

/**
 * What an automatic playback tick does next: seek to the following frame, wrap to
 * the first one when looping past the last frame, or stop there otherwise. The wrap
 * is a full step of its own, so frame 0 stays on screen for one frame interval.
 */
export function resolveNextPlaybackFrame(
  current: number,
  last: number,
  loop: boolean,
): PlaybackStep {
  if (current >= last) {
    return loop ? { action: "seek", frame: 0 } : { action: "stop" };
  }
  return { action: "seek", frame: current + 1 };
}

/**
 * Whether a window-level Home keydown must be left alone: a widget already handled
 * it (bits-ui's slider thumb jumps to its minimum on Home) or it targets a slider.
 */
export function homeShortcutIsTaken(event: {
  defaultPrevented: boolean;
  target: EventTarget | null;
}): boolean {
  if (event.defaultPrevented) return true;
  const target = event.target;
  return typeof (target as Element | null)?.closest === "function"
    ? (target as Element).closest('[role="slider"]') !== null
    : false;
}
