/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Video time, formatted with plain arithmetic: no `Date`, so the readout does not depend
 * on the time zone, and hours show once a clip passes one hour.
 */

/** `mm:ss.mmm` (or `h:mm:ss.mmm` from one hour) for `seconds`, rounded to `decimals`. */
export function formatTimecode(seconds: number, decimals: 0 | 1 | 2 | 3 = 3): string {
  const scale = 10 ** decimals;
  // Round once, in whole units of the last digit, so 59.9996 s carries into 01:00.000.
  const units = Number.isFinite(seconds) && seconds > 0 ? Math.round(seconds * scale) : 0;
  const totalSeconds = Math.floor(units / scale);
  const fraction = units - totalSeconds * scale;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  const pad2 = (value: number) => String(value).padStart(2, "0");
  const clock =
    hours > 0 ? `${hours}:${pad2(minutes)}:${pad2(secs)}` : `${pad2(minutes)}:${pad2(secs)}`;
  return decimals > 0 ? `${clock}.${String(fraction).padStart(decimals, "0")}` : clock;
}

/** The time of `frame` at `fps`, in seconds; 0 when the rate is not usable. */
export function frameTime(frame: number, fps: number): number {
  return fps > 0 && Number.isFinite(fps) ? frame / fps : 0;
}

/** A frame of a sequence view, as far as its timing goes. */
export interface TimedFrame {
  readonly data: { readonly frame_index?: number; readonly timestamp: number };
}

/**
 * Frames per second of a sequence view, from its stored timestamps (seconds, stamped at
 * import as frame_index / fps). Uses the frame indexes, not the frame count, so a view
 * with missing frames keeps its rate. Undefined when it cannot be known: fewer than two
 * frames, or timestamps all equal (fps-unknown imports).
 */
export function fpsFromSequenceFrames(frames: ReadonlyArray<TimedFrame>): number | undefined {
  if (frames.length < 2) return undefined;
  const first = frames[0].data;
  const last = frames[frames.length - 1].data;
  const timeSpan = last.timestamp - first.timestamp;
  const indexSpan =
    Number.isFinite(first.frame_index) && Number.isFinite(last.frame_index)
      ? last.frame_index - first.frame_index
      : frames.length - 1;
  if (!(timeSpan > 0) || !(indexSpan > 0)) return undefined;
  return indexSpan / timeSpan;
}

/** A frame rate for display: two decimals at most, no trailing zeros ("30", "29.97", "12.5"). */
export function formatFps(fps: number): string {
  return String(Math.round(fps * 100) / 100);
}
