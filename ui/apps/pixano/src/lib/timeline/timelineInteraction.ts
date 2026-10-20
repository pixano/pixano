/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What timeline clicks, drags and keys may do. A timeline click never cancels a drawing
 * session, which a tool switch does, and never moves the shape of an open save form to
 * another frame, since the form saves on the frame shown at Confirm.
 */

import { ToolType } from "$lib/types/tools";

// ─── Policy ─────────────────────────────────────────────────────────────────

/** Why the timeline neither seeks nor edits while the save form is open. */
export const SAVE_FORM_REASON = "Save or cancel the new shape first";
/** Why a keyframe cannot be dragged during playback. */
export const PLAYING_RETIME_REASON = "Pause the video to retime";

/** The workspace state the timeline policy depends on. */
export interface TimelineModeInput {
  readonly toolType: ToolType;
  /** Box tracking, mask tracking or a detection review in progress. */
  readonly sessionActive: boolean;
  /** The save form is open. */
  readonly saving: boolean;
  readonly playing: boolean;
  /** `editModeBlockedReason()`: sessions, detection review, Fusion. */
  readonly blockedReason: string | null;
}

/** What timeline clicks, drags and menus may do. */
export interface TimelinePolicy {
  /** Switch the drawing tool to Pan, the only tool under which selection works. */
  readonly leavesDrawingTool: boolean;
  /** Select the clicked object. */
  readonly selects: boolean;
  /** Move the playhead. */
  readonly seeks: boolean;
  /** Drag a keyframe to another frame. */
  readonly retime: boolean;
  /** The full track menu, or a notice that gives `reason`. */
  readonly menu: "full" | "notice";
  /** Why something is blocked: the save form, else `blockedReason`, else playback; or null. */
  readonly reason: string | null;
}

/** What timeline clicks, drags and menus may do in the current mode. */
export function timelinePolicy(input: TimelineModeInput): TimelinePolicy {
  const { toolType, sessionActive, saving, playing, blockedReason } = input;
  const drawing = toolType !== ToolType.Pan && toolType !== ToolType.Fusion;
  const blocked = blockedReason !== null;
  let reason: string | null = null;
  if (saving) reason = SAVE_FORM_REASON;
  else if (blocked) reason = blockedReason;
  else if (playing) reason = PLAYING_RETIME_REASON;
  return {
    leavesDrawingTool: drawing && !sessionActive && !saving,
    selects: !sessionActive && !saving,
    seeks: !saving,
    retime: !blocked && !saving && !playing && !sessionActive,
    menu: blocked || saving ? "notice" : "full",
    reason,
  };
}

// ─── Keyframe drag ──────────────────────────────────────────────────────────

/** How far, in px, a press on a tick travels before it becomes a drag. */
export const DRAG_THRESHOLD_PX = 3;

/** The frames a dragged keyframe may land on, both inclusive. */
export interface DragBounds {
  readonly min: number;
  readonly max: number;
}

/** A press on a keyframe tick: a click until it travels the threshold, then a drag. */
export type DragState =
  | { readonly phase: "idle" }
  | {
      readonly phase: "pressed";
      readonly startX: number;
      /** The pressed keyframe. */
      readonly source: number;
      /** Null when the tick can only be clicked. */
      readonly bounds: DragBounds | null;
    }
  | {
      readonly phase: "dragging";
      readonly startX: number;
      readonly source: number;
      readonly bounds: DragBounds;
      /** The frame the keyframe lands on if released now. */
      readonly preview: number;
    };

/** What happens during a press: a pointer move (`x` in the press's px), a release or a cancel. */
export type DragInput =
  | { readonly type: "move"; readonly x: number; readonly pxPerFrame: number }
  | { readonly type: "up" }
  | { readonly type: "escape" }
  | { readonly type: "cancel" };

/** What the timeline does after a drag input. */
export type DragEffect =
  | { readonly type: "none" }
  | { readonly type: "click"; readonly frame: number }
  | { readonly type: "preview"; readonly frame: number }
  | { readonly type: "commit"; readonly from: number; readonly to: number }
  | { readonly type: "cancelled" };

/** A drag state and what to do on reaching it. */
export interface DragStep {
  readonly state: DragState;
  readonly effect: DragEffect;
}

/** A press on the keyframe `source` at `x`; null bounds make the tick click-only. */
export function pressKeyframe(x: number, source: number, bounds: DragBounds | null): DragState {
  return { phase: "pressed", startX: x, source, bounds };
}

/**
 * The next drag state and its effect. A press becomes a drag once the pointer travels
 * `thresholdPx`, and only with bounds; the preview is the frame under the pointer, clamped
 * to them. A release commits a moved keyframe, or clicks when the press never became a
 * drag. Escape and cancel never commit. A move that maps to no frame is ignored.
 */
export function reduceKeyframeDrag(
  state: DragState,
  input: DragInput,
  thresholdPx: number = DRAG_THRESHOLD_PX,
): DragStep {
  if (state.phase === "idle") return stay(state);
  if (input.type === "escape" || input.type === "cancel") return settle({ type: "cancelled" });
  if (input.type === "up") {
    if (state.phase === "pressed") return settle({ type: "click", frame: state.source });
    return settle(
      state.preview !== state.source
        ? { type: "commit", from: state.source, to: state.preview }
        : { type: "none" },
    );
  }
  if (state.phase === "pressed") {
    if (!state.bounds || Math.abs(input.x - state.startX) < thresholdPx) return stay(state);
    const preview = previewFrame(state, input, state.bounds);
    if (preview === null) return stay(state);
    return {
      state: {
        phase: "dragging",
        startX: state.startX,
        source: state.source,
        bounds: state.bounds,
        preview,
      },
      effect: { type: "preview", frame: preview },
    };
  }
  const preview = previewFrame(state, input, state.bounds);
  if (preview === null || preview === state.preview) return stay(state);
  return { state: { ...state, preview }, effect: { type: "preview", frame: preview } };
}

function stay(state: DragState): DragStep {
  return { state, effect: { type: "none" } };
}

function settle(effect: DragEffect): DragStep {
  return { state: { phase: "idle" }, effect };
}

/** The frame under the pointer, clamped to `bounds`; null when the move maps to no frame. */
function previewFrame(
  press: { readonly startX: number; readonly source: number },
  move: { readonly x: number; readonly pxPerFrame: number },
  bounds: DragBounds,
): number | null {
  if (!(move.pxPerFrame > 0)) return null;
  const frame = Math.round(press.source + (move.x - press.startX) / move.pxPerFrame);
  return Number.isFinite(frame) ? Math.min(bounds.max, Math.max(bounds.min, frame)) : null;
}

// ─── Keys ───────────────────────────────────────────────────────────────────

/** What the key rules read from an event target (structural, so tests pass plain objects). */
export interface KeyTargetLike {
  readonly tagName?: string;
  readonly isContentEditable?: boolean;
  getAttribute?(name: string): string | null;
  closest?(selector: string): unknown;
}

/** What the key rules read from a keydown event; a DOM `KeyboardEvent` is one. */
export interface KeyLike {
  readonly key: string;
  readonly shiftKey: boolean;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly altKey: boolean;
  readonly defaultPrevented: boolean;
  readonly target: KeyTargetLike | EventTarget | null;
}

const TEXT_ENTRY_TAGS: ReadonlySet<string> = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** Whether a key goes to a text field or a slider, which keep their keys. */
export function isTextOrSliderTarget(target: KeyTargetLike | EventTarget | null): boolean {
  if (!target) return false;
  const element = target as KeyTargetLike;
  return (
    TEXT_ENTRY_TAGS.has(element.tagName?.toUpperCase() ?? "") ||
    element.isContentEditable === true ||
    element.getAttribute?.("role") === "slider" ||
    Boolean(element.closest?.('[role="slider"]'))
  );
}

/** -1 for J (previous keyframe), 1 for K (next), in either case; null when the key is not ours. */
export function keyframeNavDirection(event: KeyLike): -1 | 1 | null {
  if (event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return null;
  if (event.defaultPrevented) return null;
  const key = event.key?.toLowerCase();
  if (key !== "j" && key !== "k") return null;
  if (isTextOrSliderTarget(event.target)) return null;
  return key === "j" ? -1 : 1;
}

// ─── Tooltip ────────────────────────────────────────────────────────────────

/** A tick's tooltip, `#50 · 00:01.667`, naming the cameras that share it when there are several. */
export function formatTickTooltip(frame: number, time: string, views?: readonly string[]): string {
  const label = `#${frame} · ${time}`;
  return views && views.length > 1 ? `${label} · ${views.join(", ")}` : label;
}
