/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ToolContext, ToolEvent, ToolFSM, ToolState, ToolTransition } from "../types";

/**
 * Pan tool — allows panning/dragging the canvas.
 * No document mutations. Just state tracking for cursor changes.
 */
export class PanToolFSM implements ToolFSM {
  readonly id = "pan";
  readonly name = "Move image";
  readonly icon = "pan";
  readonly defaultCursor = "move";

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          return {
            newState: { phase: "drawing", origin: event.position, current: event.position },
            sideEffects: [{ type: "setCursor", cursor: "grabbing" }],
          };
        }
        break;

      case "drawing":
        if (event.type === "pointerMove") {
          return {
            newState: { phase: "drawing", origin: state.origin, current: event.position },
            sideEffects: [],
          };
        }
        if (event.type === "pointerUp") {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "setCursor", cursor: "move" }],
          };
        }
        if (event.type === "cancel") {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "setCursor", cursor: "move" }],
          };
        }
        break;
    }

    return { newState: state, sideEffects: [] };
  }
}
