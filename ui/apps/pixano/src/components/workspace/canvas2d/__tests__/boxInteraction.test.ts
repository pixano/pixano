/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  boxContainsPoint,
  boxStableKey,
  chipAnchorPoint,
  computeBoxHoverCursor,
  findBoxByStableKey,
  isEditToggleKey,
  isFinishEditKey,
  isInOverlay,
  isInteractiveBox,
  pickBoxAtPoint,
  resolveKeyboardEditTarget,
  viewNameOfNode,
  type BoxLike,
  type NodeLike,
} from "../boxInteraction";
import { PREVIEW_TABLE_NAME } from "$lib/stores/trackEditing";

function box(
  id: string,
  coords: number[],
  options: {
    editing?: boolean;
    hidden?: boolean;
    highlighted?: string;
    view?: string;
    trackletId?: string;
    preview?: boolean;
  } = {},
): BoxLike {
  return {
    id,
    data: { coords, view_name: options.view ?? "camera", tracklet_id: options.trackletId },
    table_info: { name: options.preview ? PREVIEW_TABLE_NAME : "bboxes" },
    ui: {
      displayControl: {
        hidden: options.hidden ?? false,
        editing: options.editing ?? false,
        highlighted: options.highlighted ?? "all",
      },
    },
  };
}

describe("pickBoxAtPoint", () => {
  const big = box("big", [0, 0, 100, 100]);
  const small = box("small", [40, 40, 10, 10]);

  it("picks the smallest box containing the point, whatever the order", () => {
    expect(pickBoxAtPoint([big, small], { x: 45, y: 45 })).toBe(small);
    expect(pickBoxAtPoint([small, big], { x: 45, y: 45 })).toBe(small);
    expect(pickBoxAtPoint([big, small], { x: 10, y: 10 })).toBe(big);
    expect(pickBoxAtPoint([big, small], { x: 150, y: 10 })).toBeUndefined();
  });

  it("includes the edges and tolerates negative sizes", () => {
    expect(boxContainsPoint(small, { x: 50, y: 40 })).toBe(true);
    expect(boxContainsPoint(box("flipped", [50, 50, -10, -10]), { x: 45, y: 45 })).toBe(true);
  });

  it("breaks ties for the edited box, then for the later one", () => {
    const first = box("first", [0, 0, 10, 10]);
    const second = box("second", [0, 0, 10, 10]);
    const edited = box("edited", [0, 0, 10, 10], { editing: true });
    expect(pickBoxAtPoint([first, second], { x: 5, y: 5 })).toBe(second);
    expect(pickBoxAtPoint([edited, first, second], { x: 5, y: 5 })).toBe(edited);
  });

  it("ignores hidden boxes and previews", () => {
    const hidden = box("hidden", [40, 40, 10, 10], { hidden: true });
    const preview = box("preview", [40, 40, 10, 10], { preview: true });
    expect(isInteractiveBox(hidden)).toBe(false);
    expect(isInteractiveBox(preview)).toBe(false);
    expect(pickBoxAtPoint([big, hidden, preview], { x: 45, y: 45 })).toBe(big);
  });
});

describe("boxStableKey", () => {
  it("keys a track's keyframe and interpolated box alike, other boxes by id", () => {
    const keyframe = box("kf", [0, 0, 1, 1], { trackletId: "t1" });
    const ghost = box("kf::5", [0, 0, 1, 1], { trackletId: "t1" });
    expect(boxStableKey(keyframe)).toBe("track:t1");
    expect(boxStableKey(ghost)).toBe(boxStableKey(keyframe));
    expect(boxStableKey(box("image-box", [0, 0, 1, 1], { trackletId: "" }))).toBe("box:image-box");
  });

  it("finds the current box for a key, skipping hidden ones", () => {
    const ghost = box("kf::5", [0, 0, 1, 1], { trackletId: "t1" });
    expect(findBoxByStableKey([ghost], "track:t1")).toBe(ghost);
    expect(findBoxByStableKey([ghost], null)).toBeUndefined();
    const hidden = box("h", [0, 0, 1, 1], { hidden: true });
    expect(findBoxByStableKey([hidden], "box:h")).toBeUndefined();
  });
});

describe("viewNameOfNode", () => {
  const node = (id: string, parent: NodeLike | null): NodeLike => ({
    id: () => id,
    getParent: () => parent,
  });

  it("walks up to the active view group", () => {
    const group = node("active-left", node("", null));
    expect(viewNameOfNode(node("", node("", group)))).toBe("left");
    expect(viewNameOfNode(node("image-left", null))).toBeUndefined();
    expect(viewNameOfNode(null)).toBeUndefined();
  });
});

describe("keyboard", () => {
  const key = (k: string, extra: Partial<Parameters<typeof isEditToggleKey>[0]> = {}) => ({
    key: k,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    repeat: false,
    ...extra,
  });

  it("toggles on a plain E only", () => {
    expect(isEditToggleKey(key("e"))).toBe(true);
    expect(isEditToggleKey(key("E"))).toBe(true);
    expect(isEditToggleKey(key("e", { ctrlKey: true }))).toBe(false);
    expect(isEditToggleKey(key("e", { metaKey: true }))).toBe(false);
    expect(isEditToggleKey(key("e", { repeat: true }))).toBe(false);
    expect(isEditToggleKey(key("r"))).toBe(false);
  });

  it("finishes on Enter without Ctrl, Cmd or Alt", () => {
    expect(isFinishEditKey(key("Enter"))).toBe(true);
    expect(isFinishEditKey(key("Enter", { ctrlKey: true }))).toBe(false);
    expect(isFinishEditKey(key("Enter", { metaKey: true }))).toBe(false);
    expect(isFinishEditKey(key("Enter", { altKey: true }))).toBe(false);
    expect(isFinishEditKey(key("Escape"))).toBe(false);
  });

  it("leaves Enter to dialogs, menus and list boxes", () => {
    // An element whose closest ancestor with a role has `role`, if any.
    const inside = (role?: string) => ({
      closest: (selectors: string) =>
        role !== undefined && selectors.includes(`[role="${role}"]`) ? {} : null,
    });
    expect(isInOverlay(inside("dialog"))).toBe(true);
    expect(isInOverlay(inside("alertdialog"))).toBe(true);
    expect(isInOverlay(inside("menu"))).toBe(true);
    expect(isInOverlay(inside("listbox"))).toBe(true);
    expect(isInOverlay(inside("tab"))).toBe(false);
    expect(isInOverlay(inside())).toBe(false);
    // The window and the document are targets without `closest`.
    expect(isInOverlay({})).toBe(false);
    expect(isInOverlay(null)).toBe(false);
  });

  it("targets the pointed box, else the focused entity's edited, pointer-view, first box", () => {
    const pointed = box("pointed", [0, 0, 1, 1]);
    const focusedLeft = box("fl", [0, 0, 1, 1], { highlighted: "self", view: "left" });
    const focusedRight = box("fr", [0, 0, 1, 1], { highlighted: "self", view: "right" });
    const edited = box("fe", [0, 0, 1, 1], { highlighted: "self", view: "right", editing: true });
    const boxes = [pointed, focusedRight, focusedLeft];
    const viewOrder = ["left", "right"];

    expect(resolveKeyboardEditTarget(boxes, { pointedKey: "box:pointed", viewOrder })).toBe(
      pointed,
    );
    expect(resolveKeyboardEditTarget(boxes, { pointedKey: null, viewOrder })).toBe(focusedLeft);
    expect(
      resolveKeyboardEditTarget(boxes, { pointedKey: null, pointerView: "right", viewOrder }),
    ).toBe(focusedRight);
    expect(resolveKeyboardEditTarget([...boxes, edited], { pointedKey: null, viewOrder })).toBe(
      edited,
    );
    expect(resolveKeyboardEditTarget([pointed], { pointedKey: null, viewOrder })).toBeUndefined();
  });
});

describe("cursor and chip anchor", () => {
  it("shows move over the edited box and pointer over others", () => {
    expect(computeBoxHoverCursor(box("e", [0, 0, 1, 1], { editing: true }))).toBe("move");
    expect(computeBoxHoverCursor(box("b", [0, 0, 1, 1]))).toBe("pointer");
    expect(computeBoxHoverCursor(undefined)).toBeNull();
  });

  it("anchors on the top-right corner of the visible part of the box", () => {
    const container = { x: 100, y: 50, width: 400, height: 300 };
    expect(chipAnchorPoint({ x: 150, y: 100, width: 50, height: 40 }, container)).toEqual({
      x: 200,
      y: 100,
    });
    // Partly above and right of the canvas: clamped to its edges.
    expect(chipAnchorPoint({ x: 450, y: 20, width: 100, height: 60 }, container)).toEqual({
      x: 500,
      y: 50,
    });
    expect(chipAnchorPoint({ x: 600, y: 100, width: 10, height: 10 }, container)).toBeNull();
  });
});
