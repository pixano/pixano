/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolSideEffect,
  ToolState,
  ToolTransition,
} from "../types";

/**
 * Brush tool — for painting/erasing masks.
 *
 * States: idle → brushing → idle
 *
 * Mouse down starts brush stroke, mouse move adds points,
 * mouse up completes the stroke and emits a mask command.
 */
export class BrushToolFSM implements ToolFSM {
  readonly id: string;
  readonly name: string;
  readonly icon = "brush";
  readonly defaultCursor = "none"; // Custom cursor rendered in preview layer
  readonly mode: "draw" | "erase";

  constructor(mode: "draw" | "erase" = "draw") {
    this.mode = mode;
    this.id = mode === "draw" ? "brush-draw" : "brush-erase";
    this.name = mode === "draw" ? "Brush (Draw)" : "Brush (Erase)";
  }

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, _context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          return {
            newState: { phase: "brushing", path: [event.position] },
            sideEffects: [
              { type: "beginTransaction", description: `Brush ${this.mode}` },
              {
                type: "updatePreview",
                preview: {
                  type: "brush",
                  path: [event.position],
                  radius: 10, // Default; will be overridden by brush settings
                },
              },
            ],
          };
        }
        break;

      case "brushing": {
        const path = state.path;

        if (event.type === "pointerMove") {
          const newPath = [...path, event.position];
          return {
            newState: { phase: "brushing", path: newPath },
            sideEffects: [
              {
                type: "updatePreview",
                preview: { type: "brush", path: newPath, radius: 10 },
              },
            ],
          };
        }

        if (event.type === "pointerUp") {
          const sideEffects: ToolSideEffect[] = [
            { type: "updatePreview", preview: null },
            { type: "commitTransaction" },
          ];

          return { newState: { phase: "idle" }, sideEffects };
        }

        if (event.type === "cancel") {
          return {
            newState: { phase: "idle" },
            sideEffects: [
              { type: "updatePreview", preview: null },
              { type: "abortTransaction" },
            ],
          };
        }
        break;
      }
    }

    return { newState: state, sideEffects: [] };
  }
}
