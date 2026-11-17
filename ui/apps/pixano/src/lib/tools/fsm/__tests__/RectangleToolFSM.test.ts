/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { RectangleToolFSM } from "../RectangleToolFSM";
import type { ToolContext, ToolState } from "$lib/types/tools";

const context = {} as ToolContext;

function draw(fsm: RectangleToolFSM) {
  let state: ToolState = fsm.getInitialState();
  state = fsm.transition(
    state,
    { type: "pointerDown", position: { x: 50, y: 40 }, button: 0 },
    context,
  ).newState;
  state = fsm.transition(
    state,
    { type: "pointerMove", position: { x: 10, y: 20 } },
    context,
  ).newState;
  return fsm.transition(state, { type: "pointerUp", position: { x: 10, y: 20 } }, context);
}

describe("RectangleToolFSM", () => {
  it("waits for Enter before saving a drawn box", () => {
    const transition = draw(new RectangleToolFSM());
    expect(transition.newState.phase).toBe("editingNew");
    expect(transition.sideEffects.some((effect) => effect.type === "requestSave")).toBe(false);
  });

  it("saves a drawn box at once with autoConfirm, ready for the next one", () => {
    const transition = draw(new RectangleToolFSM({ autoConfirm: true }));
    expect(transition.newState.phase).toBe("idle");
    expect(transition.sideEffects).toContainEqual({
      type: "requestSave",
      shapeType: "bbox",
      geometry: { x: 10, y: 20, width: 40, height: 20 },
    });
  });
});
