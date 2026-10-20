/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import {
  DRAG_THRESHOLD_PX,
  formatTickTooltip,
  isTextOrSliderTarget,
  keyframeNavDirection,
  PLAYING_RETIME_REASON,
  pressKeyframe,
  reduceKeyframeDrag,
  SAVE_FORM_REASON,
  timelinePolicy,
  type DragEffect,
  type DragInput,
  type DragState,
  type KeyLike,
  type TimelineModeInput,
} from "../timelineInteraction";
import { ToolType } from "$lib/types/tools";

const SESSION_REASON = "Finish or cancel the tracking session first";
const FUSION_REASON = "Leave association mode first";

describe("timelinePolicy", () => {
  const idle: TimelineModeInput = {
    toolType: ToolType.Pan,
    sessionActive: false,
    saving: false,
    playing: false,
    blockedReason: null,
  };
  const policy = (patch: Partial<TimelineModeInput>) => timelinePolicy({ ...idle, ...patch });

  it("only seeks during a tracking session, so the session survives", () => {
    expect(
      policy({ toolType: ToolType.Rectangle, sessionActive: true, blockedReason: SESSION_REASON }),
    ).toEqual({
      leavesDrawingTool: false,
      selects: false,
      seeks: true,
      retime: false,
      menu: "notice",
      reason: SESSION_REASON,
    });
  });

  it("does nothing while the save form is open, so the shape keeps its frame", () => {
    expect(policy({ toolType: ToolType.Polygon, saving: true })).toEqual({
      leavesDrawingTool: false,
      selects: false,
      seeks: false,
      retime: false,
      menu: "notice",
      reason: SAVE_FORM_REASON,
    });
  });

  it("leaves an idle drawing tool for Pan and allows everything", () => {
    expect(policy({ toolType: ToolType.Polygon })).toEqual({
      leavesDrawingTool: true,
      selects: true,
      seeks: true,
      retime: true,
      menu: "full",
      reason: null,
    });
  });

  it("allows everything under an idle Pan, which it keeps", () => {
    expect(policy({})).toEqual({
      leavesDrawingTool: false,
      selects: true,
      seeks: true,
      retime: true,
      menu: "full",
      reason: null,
    });
  });

  it("blocks only retime during playback, and says why", () => {
    expect(policy({ playing: true })).toEqual({
      leavesDrawingTool: false,
      selects: true,
      seeks: true,
      retime: false,
      menu: "full",
      reason: PLAYING_RETIME_REASON,
    });
  });

  it("keeps Fusion, and its menu gives the reason", () => {
    expect(policy({ toolType: ToolType.Fusion, blockedReason: FUSION_REASON })).toEqual({
      leavesDrawingTool: false,
      selects: true,
      seeks: true,
      retime: false,
      menu: "notice",
      reason: FUSION_REASON,
    });
  });

  const drawingTools = Object.values(ToolType).filter(
    (toolType) => toolType !== ToolType.Pan && toolType !== ToolType.Fusion,
  );

  it.each(drawingTools)("leaves %s for Pan only without a session or a save form", (toolType) => {
    expect(policy({ toolType }).leavesDrawingTool).toBe(true);
    expect(policy({ toolType, sessionActive: true }).leavesDrawingTool).toBe(false);
    expect(policy({ toolType, saving: true }).leavesDrawingTool).toBe(false);
  });

  it("never leaves Pan or Fusion", () => {
    expect(policy({ toolType: ToolType.Pan }).leavesDrawingTool).toBe(false);
    expect(policy({ toolType: ToolType.Fusion }).leavesDrawingTool).toBe(false);
  });

  it("gives the save form's reason first, then the blocked reason, then playback's", () => {
    const all = { saving: true, playing: true, sessionActive: true, blockedReason: SESSION_REASON };
    expect(policy(all)).toEqual({
      leavesDrawingTool: false,
      selects: false,
      seeks: false,
      retime: false,
      menu: "notice",
      reason: SAVE_FORM_REASON,
    });
    expect(policy({ playing: true, blockedReason: SESSION_REASON }).reason).toBe(SESSION_REASON);
  });

  it("follows the rules for every tool and state", () => {
    const failures: string[] = [];
    for (const toolType of Object.values(ToolType)) {
      for (const sessionActive of [false, true]) {
        for (const saving of [false, true]) {
          for (const playing of [false, true]) {
            for (const blockedReason of [null, FUSION_REASON]) {
              const input = { toolType, sessionActive, saving, playing, blockedReason };
              const drawing = toolType !== ToolType.Pan && toolType !== ToolType.Fusion;
              let reason: string | null = null;
              if (saving) reason = SAVE_FORM_REASON;
              else if (blockedReason !== null) reason = blockedReason;
              else if (playing) reason = PLAYING_RETIME_REASON;
              const expected = {
                leavesDrawingTool: drawing && !sessionActive && !saving,
                selects: !sessionActive && !saving,
                seeks: !saving,
                retime: blockedReason === null && !saving && !playing && !sessionActive,
                menu: blockedReason !== null || saving ? "notice" : "full",
                reason,
              };
              const actual = timelinePolicy(input);
              if (JSON.stringify(actual) !== JSON.stringify(expected)) {
                failures.push(`${JSON.stringify(input)}: ${JSON.stringify(actual)}`);
              }
            }
          }
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("never retimes during a session, even without a blocked reason", () => {
    expect(policy({ sessionActive: true })).toEqual({
      leavesDrawingTool: false,
      selects: false,
      seeks: true,
      retime: false,
      menu: "full",
      reason: null,
    });
  });
});

describe("reduceKeyframeDrag", () => {
  const bounds = { min: 13, max: 24 };
  const pressed = pressKeyframe(100, 20, bounds);
  const move = (x: number, pxPerFrame = 2): DragInput => ({ type: "move", x, pxPerFrame });
  const up: DragInput = { type: "up" };
  const escape: DragInput = { type: "escape" };
  const cancel: DragInput = { type: "cancel" };
  const none: DragEffect = { type: "none" };
  const cancelled: DragEffect = { type: "cancelled" };
  const preview = (frame: number): DragEffect => ({ type: "preview", frame });

  /** Feeds `inputs` in order; returns the last state and every effect. */
  function run(start: DragState, inputs: DragInput[]) {
    let state = start;
    const effects: DragEffect[] = [];
    for (const input of inputs) {
      const step = reduceKeyframeDrag(state, input);
      state = step.state;
      effects.push(step.effect);
    }
    return { state, effects };
  }

  it("presses a keyframe", () => {
    expect(pressed).toEqual({ phase: "pressed", startX: 100, source: 20, bounds });
    expect(pressKeyframe(5, 0, null)).toEqual({
      phase: "pressed",
      startX: 5,
      source: 0,
      bounds: null,
    });
  });

  it("clicks when the pointer stays under the threshold", () => {
    expect(run(pressed, [move(102), up])).toEqual({
      state: { phase: "idle" },
      effects: [none, { type: "click", frame: 20 }],
    });
    expect(reduceKeyframeDrag(pressed, move(98))).toEqual({ state: pressed, effect: none });
    expect(reduceKeyframeDrag(pressed, move(102.9)).state).toBe(pressed);
  });

  it("drags from the threshold on, and previews the frame under the pointer", () => {
    expect(DRAG_THRESHOLD_PX).toBe(3);
    expect(reduceKeyframeDrag(pressed, move(104))).toEqual({
      state: { phase: "dragging", startX: 100, source: 20, bounds, preview: 22 },
      effect: preview(22),
    });
    // 3 px at 10 px per frame: the drag starts on the source frame.
    expect(reduceKeyframeDrag(pressed, move(103, 10))).toEqual({
      state: { phase: "dragging", startX: 100, source: 20, bounds, preview: 20 },
      effect: preview(20),
    });
    expect(reduceKeyframeDrag(pressed, move(97)).effect).toEqual(preview(19));
  });

  it("takes another threshold", () => {
    expect(reduceKeyframeDrag(pressed, move(105), 6).state).toBe(pressed);
    expect(reduceKeyframeDrag(pressed, move(94), 6).effect).toEqual(preview(17));
    expect(reduceKeyframeDrag(pressed, move(101), 0).effect).toEqual(preview(21));
  });

  it("clamps the preview to the bounds", () => {
    expect(run(pressed, [move(104), move(1000)]).state).toMatchObject({ preview: 24 });
    expect(run(pressed, [move(104), move(-1000)]).state).toMatchObject({ preview: 13 });
    expect(reduceKeyframeDrag(pressed, move(1000)).effect).toEqual(preview(24));
    expect(run(pressed, [move(1000), move(2000)]).effects).toEqual([preview(24), none]);
  });

  it("previews the rounded travel, clamped, at every distance and scale", () => {
    const failures: string[] = [];
    for (const pxPerFrame of [0.25, 1, 2, 7.3, 40]) {
      for (let dx = -120; dx <= 120; dx += 0.5) {
        const step = reduceKeyframeDrag(pressed, move(100 + dx, pxPerFrame));
        const expected =
          Math.abs(dx) < DRAG_THRESHOLD_PX
            ? pressed
            : {
                phase: "dragging",
                startX: 100,
                source: 20,
                bounds,
                preview: Math.min(24, Math.max(13, Math.round(20 + dx / pxPerFrame))),
              };
        if (JSON.stringify(step.state) !== JSON.stringify(expected)) {
          failures.push(`dx ${dx} at ${pxPerFrame} px/frame: ${JSON.stringify(step.state)}`);
        }
      }
    }
    expect(failures).toEqual([]);
  });

  it("previews a frame change only", () => {
    const { state: dragging } = reduceKeyframeDrag(pressed, move(104));
    expect(reduceKeyframeDrag(dragging, move(104.8))).toEqual({ state: dragging, effect: none });
    expect(reduceKeyframeDrag(dragging, move(104.8)).state).toBe(dragging);
    expect(reduceKeyframeDrag(dragging, move(106))).toEqual({
      state: { phase: "dragging", startX: 100, source: 20, bounds, preview: 23 },
      effect: preview(23),
    });
  });

  it("follows the pointer back under the threshold once dragging", () => {
    expect(run(pressed, [move(104), move(101)]).effects).toEqual([preview(22), preview(21)]);
  });

  it("maps the travel since the press with the current scale", () => {
    expect(run(pressed, [move(104), move(110, 10)]).state).toMatchObject({ preview: 21 });
  });

  it("commits a moved keyframe on release", () => {
    expect(run(pressed, [move(104), up])).toEqual({
      state: { phase: "idle" },
      effects: [preview(22), { type: "commit", from: 20, to: 22 }],
    });
  });

  it("commits nothing when the keyframe is dropped back on its frame", () => {
    expect(run(pressed, [move(104), move(100), up])).toEqual({
      state: { phase: "idle" },
      effects: [preview(22), preview(20), none],
    });
  });

  it("cancels a drag on Escape, and a later release does nothing", () => {
    expect(run(pressed, [move(104), escape, up])).toEqual({
      state: { phase: "idle" },
      effects: [preview(22), cancelled, none],
    });
  });

  it("cancels a press or a drag without committing", () => {
    expect(reduceKeyframeDrag(pressed, cancel)).toEqual({
      state: { phase: "idle" },
      effect: cancelled,
    });
    expect(reduceKeyframeDrag(pressed, escape)).toEqual({
      state: { phase: "idle" },
      effect: cancelled,
    });
    expect(run(pressed, [move(104), cancel, up]).effects).toEqual([preview(22), cancelled, none]);
  });

  it("keeps a tick without bounds a click", () => {
    const clickOnly = pressKeyframe(100, 20, null);
    expect(reduceKeyframeDrag(clickOnly, move(110))).toEqual({ state: clickOnly, effect: none });
    expect(reduceKeyframeDrag(clickOnly, move(110)).state).toBe(clickOnly);
    expect(run(clickOnly, [move(110), move(50), up])).toEqual({
      state: { phase: "idle" },
      effects: [none, none, { type: "click", frame: 20 }],
    });
    expect(reduceKeyframeDrag(clickOnly, escape).effect).toEqual(cancelled);
  });

  it("ignores every input when idle", () => {
    const idle: DragState = { phase: "idle" };
    for (const input of [move(500), up, escape, cancel]) {
      const step = reduceKeyframeDrag(idle, input);
      expect(step.state).toBe(idle);
      expect(step.effect).toEqual(none);
    }
  });

  it("ignores a move that maps to no frame", () => {
    expect(reduceKeyframeDrag(pressed, move(110, 0)).state).toBe(pressed);
    expect(reduceKeyframeDrag(pressed, move(110, -2)).state).toBe(pressed);
    expect(reduceKeyframeDrag(pressed, move(Number.NaN)).state).toBe(pressed);
    const { state: dragging } = reduceKeyframeDrag(pressed, move(104));
    expect(reduceKeyframeDrag(dragging, move(110, Number.NaN))).toEqual({
      state: dragging,
      effect: none,
    });
    expect(reduceKeyframeDrag(dragging, move(Number.POSITIVE_INFINITY)).state).toBe(dragging);
  });
});

describe("isTextOrSliderTarget", () => {
  it("finds text fields, whatever the case of the tag", () => {
    for (const tagName of ["INPUT", "textarea", "Select"]) {
      expect(isTextOrSliderTarget({ tagName })).toBe(true);
    }
    expect(isTextOrSliderTarget({ tagName: "DIV" })).toBe(false);
    expect(isTextOrSliderTarget({ tagName: "BUTTON" })).toBe(false);
  });

  it("finds editable content", () => {
    expect(isTextOrSliderTarget({ tagName: "DIV", isContentEditable: true })).toBe(true);
    expect(isTextOrSliderTarget({ tagName: "DIV", isContentEditable: false })).toBe(false);
  });

  it("finds a slider and what lies inside one", () => {
    const role = (value: string | null) => (name: string) => (name === "role" ? value : null);
    expect(isTextOrSliderTarget({ getAttribute: role("slider") })).toBe(true);
    expect(isTextOrSliderTarget({ getAttribute: role("button") })).toBe(false);
    const closest = vi.fn((selector: string) => (selector === '[role="slider"]' ? {} : null));
    expect(isTextOrSliderTarget({ tagName: "SPAN", closest })).toBe(true);
    expect(closest).toHaveBeenCalledWith('[role="slider"]');
    expect(isTextOrSliderTarget({ tagName: "SPAN", closest: () => null })).toBe(false);
  });

  it("is false without a target, or on one that is not an element", () => {
    expect(isTextOrSliderTarget(null)).toBe(false);
    expect(isTextOrSliderTarget({})).toBe(false);
    expect(isTextOrSliderTarget(new EventTarget())).toBe(false);
  });
});

describe("keyframeNavDirection", () => {
  const press = (key: string, patch: Partial<KeyLike> = {}): KeyLike => ({
    key,
    shiftKey: false,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    defaultPrevented: false,
    target: null,
    ...patch,
  });

  it("maps J to the previous keyframe and K to the next, whatever the case", () => {
    expect(keyframeNavDirection(press("j"))).toBe(-1);
    expect(keyframeNavDirection(press("k"))).toBe(1);
    // CapsLock without Shift.
    expect(keyframeNavDirection(press("J"))).toBe(-1);
    expect(keyframeNavDirection(press("K"))).toBe(1);
  });

  it("leaves the key alone with a modifier", () => {
    expect(keyframeNavDirection(press("J", { shiftKey: true }))).toBeNull();
    expect(keyframeNavDirection(press("K", { shiftKey: true }))).toBeNull();
    expect(keyframeNavDirection(press("k", { ctrlKey: true }))).toBeNull();
    expect(keyframeNavDirection(press("k", { metaKey: true }))).toBeNull();
    expect(keyframeNavDirection(press("k", { altKey: true }))).toBeNull();
    expect(keyframeNavDirection(press("j", { ctrlKey: true, altKey: true }))).toBeNull();
  });

  it("leaves a key that another handler took", () => {
    expect(keyframeNavDirection(press("k", { defaultPrevented: true }))).toBeNull();
  });

  it("leaves the key to text fields and sliders", () => {
    expect(keyframeNavDirection(press("j", { target: { tagName: "TEXTAREA" } }))).toBeNull();
    expect(keyframeNavDirection(press("k", { target: { tagName: "input" } }))).toBeNull();
    expect(keyframeNavDirection(press("k", { target: { isContentEditable: true } }))).toBeNull();
    const slider = { getAttribute: (name: string) => (name === "role" ? "slider" : null) };
    expect(keyframeNavDirection(press("k", { target: slider }))).toBeNull();
    expect(keyframeNavDirection(press("j", { target: { closest: () => ({}) } }))).toBeNull();
  });

  it("takes J and K anywhere else", () => {
    const button = {
      tagName: "BUTTON",
      isContentEditable: false,
      getAttribute: () => null,
      closest: () => null,
    };
    expect(keyframeNavDirection(press("j", { target: button }))).toBe(-1);
    expect(keyframeNavDirection(press("k", { target: new EventTarget() }))).toBe(1);
  });

  it("ignores other keys", () => {
    for (const key of ["x", "l", "ArrowLeft", "Enter", " ", "", "jk"]) {
      expect(keyframeNavDirection(press(key))).toBeNull();
    }
  });
});

describe("formatTickTooltip", () => {
  it("gives the frame and its time", () => {
    expect(formatTickTooltip(50, "00:01.667")).toBe("#50 · 00:01.667");
    expect(formatTickTooltip(0, "00:00.000")).toBe("#0 · 00:00.000");
  });

  it("names the cameras that share the tick when there are several", () => {
    expect(formatTickTooltip(50, "00:01.667", ["left", "right"])).toBe(
      "#50 · 00:01.667 · left, right",
    );
    expect(formatTickTooltip(7, "00:00.233", ["left", "right", "top"])).toBe(
      "#7 · 00:00.233 · left, right, top",
    );
  });

  it("names no camera when one owns the tick", () => {
    expect(formatTickTooltip(50, "00:01.667", ["left"])).toBe("#50 · 00:01.667");
    expect(formatTickTooltip(50, "00:01.667", [])).toBe("#50 · 00:01.667");
  });
});
