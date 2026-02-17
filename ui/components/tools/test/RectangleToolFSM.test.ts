/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { PreviewShape, ToolState, ToolTransition } from "../src/types";
import { RectangleToolFSM } from "../src/fsm/RectangleToolFSM";
import { createTestContext } from "./helpers";

function idle(): ToolState {
  return { phase: "idle" };
}

function drawing(ox: number, oy: number, cx: number, cy: number): ToolState {
  return { phase: "drawing", origin: { x: ox, y: oy }, current: { x: cx, y: cy } };
}

function editingNew(ox: number, oy: number, cx: number, cy: number): ToolState {
  return { phase: "editingNew", origin: { x: ox, y: oy }, current: { x: cx, y: cy } };
}

describe("RectangleToolFSM", () => {
  const fsm = new RectangleToolFSM();
  const ctx = createTestContext();

  // -------- Initial State --------

  describe("initial state", () => {
    it("should start in idle", () => {
      expect(fsm.getInitialState()).toEqual({ phase: "idle" });
    });

    it("should have correct metadata", () => {
      expect(fsm.id).toBe("rectangle");
      expect(fsm.name).toBe("Rectangle selection");
      expect(fsm.defaultCursor).toBe("crosshair");
      expect(fsm.isSmart).toBe(false);
    });
  });

  // -------- idle → drawing --------

  describe("idle → drawing", () => {
    it("should transition on left pointerDown", () => {
      const result = fsm.transition(idle(), {
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      }, ctx);

      expect(result.newState.phase).toBe("drawing");
      expect(result.sideEffects).toHaveLength(1);
      expect(result.sideEffects[0].type).toBe("updatePreview");
    });

    it("should ignore right-click", () => {
      const result = fsm.transition(idle(), {
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 2,
      }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(result.sideEffects).toHaveLength(0);
    });

    it("should emit preview with origin=current on pointerDown", () => {
      const result = fsm.transition(idle(), {
        type: "pointerDown",
        position: { x: 10, y: 20 },
        button: 0,
      }, ctx);

      const preview = getPreview(result);
      expect(preview).toBeDefined();
      expect(preview?.type).toBe("rectangle");
      if (preview?.type === "rectangle") {
        expect(preview.origin).toEqual({ x: 10, y: 20 });
        expect(preview.current).toEqual({ x: 10, y: 20 });
      }
    });
  });

  // -------- drawing → drawing --------

  describe("drawing → drawing", () => {
    it("should update current on pointerMove", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerMove",
        position: { x: 100, y: 200 },
      }, ctx);

      expect(result.newState.phase).toBe("drawing");
      if (result.newState.phase === "drawing") {
        expect(result.newState.origin).toEqual({ x: 10, y: 20 });
        expect(result.newState.current).toEqual({ x: 100, y: 200 });
      }
    });

    it("should emit preview update on pointerMove", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerMove",
        position: { x: 100, y: 200 },
      }, ctx);

      const preview = getPreview(result);
      expect(preview?.type).toBe("rectangle");
      if (preview?.type === "rectangle") {
        expect(preview.origin).toEqual({ x: 10, y: 20 });
        expect(preview.current).toEqual({ x: 100, y: 200 });
      }
    });

    it("should NOT emit commands on pointerMove", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerMove",
        position: { x: 100, y: 200 },
      }, ctx);

      const commands = result.sideEffects.filter((e) => e.type === "emitCommand");
      expect(commands).toHaveLength(0);
    });
  });

  // -------- drawing → editingNew --------

  describe("drawing → editingNew", () => {
    it("should transition to editingNew on pointerUp with area", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 220 },
      }, ctx);

      expect(result.newState.phase).toBe("editingNew");
      if (result.newState.phase === "editingNew") {
        expect(result.newState.origin).toEqual({ x: 10, y: 20 });
        expect(result.newState.current).toEqual({ x: 110, y: 220 });
      }
    });

    it("should emit editable preview on pointerUp with area", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 220 },
      }, ctx);

      const preview = getPreview(result);
      expect(preview?.type).toBe("rectangle");
      if (preview?.type === "rectangle") {
        expect(preview.editable).toBe(true);
      }
    });

    it("should NOT emit AddAnnotation command", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 220 },
      }, ctx);

      const commands = result.sideEffects.filter((e) => e.type === "emitCommand");
      expect(commands).toHaveLength(0);
    });
  });

  // -------- drawing → idle (zero area) --------

  describe("drawing → idle (zero area)", () => {
    it("should go to idle on pointerUp with dx≤2", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 12, y: 220 },
      }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });

    it("should go to idle on pointerUp with dy≤2", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 22 },
      }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });

    it("should go to idle when both dx and dy are zero (click)", () => {
      const state = drawing(10, 20, 10, 20);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 10, y: 20 },
      }, ctx);

      expect(result.newState.phase).toBe("idle");
    });
  });

  // -------- drawing → idle (cancel) --------

  describe("drawing → idle (cancel)", () => {
    it("should go to idle on Escape key", () => {
      const state = drawing(10, 20, 50, 60);
      const result = fsm.transition(state, {
        type: "keyDown",
        key: "Escape",
      }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });

    it("should go to idle on cancel event", () => {
      const state = drawing(10, 20, 50, 60);
      const result = fsm.transition(state, { type: "cancel" }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });
  });

  // -------- editingNew → idle (confirm) --------

  describe("editingNew → idle (confirm)", () => {
    it("should emit requestSave with bbox geometry on confirm", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, { type: "confirm" }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();

      const saveEffects = result.sideEffects.filter((e) => e.type === "requestSave");
      expect(saveEffects).toHaveLength(1);
      if (saveEffects[0].type === "requestSave") {
        expect(saveEffects[0].shapeType).toBe("bbox");
        const geo = saveEffects[0].geometry as { x: number; y: number; width: number; height: number };
        expect(geo.x).toBe(10);
        expect(geo.y).toBe(20);
        expect(geo.width).toBe(100);
        expect(geo.height).toBe(200);
      }
    });

    it("should emit requestSave on Enter key", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, { type: "keyDown", key: "Enter" }, ctx);

      expect(result.newState.phase).toBe("idle");
      const saveEffects = result.sideEffects.filter((e) => e.type === "requestSave");
      expect(saveEffects).toHaveLength(1);
    });

    it("should normalize reversed coordinates", () => {
      // origin is bottom-right, current is top-left
      const state = editingNew(110, 220, 10, 20);
      const result = fsm.transition(state, { type: "confirm" }, ctx);

      const saveEffects = result.sideEffects.filter((e) => e.type === "requestSave");
      if (saveEffects[0].type === "requestSave") {
        const geo = saveEffects[0].geometry as { x: number; y: number; width: number; height: number };
        expect(geo.x).toBe(10);
        expect(geo.y).toBe(20);
        expect(geo.width).toBe(100);
        expect(geo.height).toBe(200);
      }
    });
  });

  // -------- editingNew → idle (cancel) --------

  describe("editingNew → idle (cancel)", () => {
    it("should clear preview on Escape", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, { type: "keyDown", key: "Escape" }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });

    it("should clear preview on cancel event", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, { type: "cancel" }, ctx);

      expect(result.newState.phase).toBe("idle");
      expect(getPreview(result)).toBeNull();
    });

    it("should not emit requestSave on cancel", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, { type: "cancel" }, ctx);

      const saveEffects = result.sideEffects.filter((e) => e.type === "requestSave");
      expect(saveEffects).toHaveLength(0);
    });
  });

  // -------- editingNew ignores pointers --------

  describe("editingNew ignores pointer events", () => {
    it("should stay in editingNew on pointerDown", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, {
        type: "pointerDown",
        position: { x: 50, y: 50 },
        button: 0,
      }, ctx);

      expect(result.newState.phase).toBe("editingNew");
      expect(result.sideEffects).toHaveLength(0);
    });

    it("should stay in editingNew on pointerMove", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, {
        type: "pointerMove",
        position: { x: 50, y: 50 },
      }, ctx);

      expect(result.newState.phase).toBe("editingNew");
    });

    it("should stay in editingNew on pointerUp", () => {
      const state = editingNew(10, 20, 110, 220);
      const result = fsm.transition(state, {
        type: "pointerUp",
        position: { x: 50, y: 50 },
      }, ctx);

      expect(result.newState.phase).toBe("editingNew");
    });
  });

  // -------- Smart mode --------

  describe("smart mode", () => {
    it("should transition to waitingForAI on pointerUp with area", () => {
      const smartFsm = new RectangleToolFSM({ isSmart: true });
      const state = drawing(10, 20, 10, 20);
      const result = smartFsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 220 },
      }, ctx);

      expect(result.newState.phase).toBe("waitingForAI");
      const aiEffects = result.sideEffects.filter((e) => e.type === "requestAI");
      expect(aiEffects).toHaveLength(1);
    });

    it("should NOT transition to editingNew in smart mode", () => {
      const smartFsm = new RectangleToolFSM({ isSmart: true });
      const state = drawing(10, 20, 10, 20);
      const result = smartFsm.transition(state, {
        type: "pointerUp",
        position: { x: 110, y: 220 },
      }, ctx);

      expect(result.newState.phase).not.toBe("editingNew");
    });
  });

  // -------- Fallthrough --------

  describe("fallthrough", () => {
    it("should return same state for unhandled events", () => {
      const state = idle();
      const result = fsm.transition(state, {
        type: "pointerMove",
        position: { x: 50, y: 50 },
      }, ctx);

      expect(result.newState).toBe(state);
      expect(result.sideEffects).toHaveLength(0);
    });
  });
});

// -------- Helpers --------

function getPreview(result: ToolTransition): PreviewShape | null {
  const effect = result.sideEffects.find((e) => e.type === "updatePreview");
  if (effect?.type === "updatePreview") {
    return effect.preview;
  }
  return undefined as unknown as PreviewShape | null;
}
