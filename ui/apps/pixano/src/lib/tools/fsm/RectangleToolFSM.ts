/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";

/**
 * Rectangle drawing tool.
 *
 * States: idle → drawing → editingNew → idle
 *
 * On pointerDown: start drawing (origin point)
 * On pointerMove while drawing: update preview rectangle
 * On pointerUp (area > 0, non-smart): transition to editingNew with editable preview
 * On pointerUp (area > 0, smart): transition to waitingForAI
 * On pointerUp (area = 0): back to idle
 * On confirm (Enter) in editingNew: emit requestSave with bbox geometry, back to idle
 * On cancel (Escape) in editingNew: clear preview, back to idle
 */
export class RectangleToolFSM implements ToolFSM {
  readonly id = "rectangle";
  readonly name = "Rectangle selection";
  readonly icon = "rectangle";
  readonly defaultCursor = "crosshair";

  /** If true, this rectangle is a smart tool that triggers AI post-processing. */
  readonly isSmart: boolean;

  constructor(options?: { isSmart?: boolean }) {
    this.isSmart = options?.isSmart ?? false;
  }

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
            sideEffects: [
              {
                type: "updatePreview",
                preview: {
                  type: "rectangle",
                  origin: event.position,
                  current: event.position,
                },
              },
            ],
          };
        }
        break;

      case "drawing":
        if (event.type === "pointerMove") {
          return {
            newState: { phase: "drawing", origin: state.origin, current: event.position },
            sideEffects: [
              {
                type: "updatePreview",
                preview: {
                  type: "rectangle",
                  origin: state.origin,
                  current: event.position,
                },
              },
            ],
          };
        }

        if (event.type === "pointerUp") {
          const dx = Math.abs(event.position.x - state.origin.x);
          const dy = Math.abs(event.position.y - state.origin.y);

          // Zero-area: discard
          if (dx <= 2 || dy <= 2) {
            return {
              newState: { phase: "idle" },
              sideEffects: [{ type: "updatePreview", preview: null }],
            };
          }

          if (this.isSmart) {
            // Smart rectangle: trigger AI inference
            const requestId = `smart-rect-${Date.now()}`;
            return {
              newState: { phase: "waitingForAI", requestId },
              sideEffects: [
                { type: "updatePreview", preview: null },
                {
                  type: "requestAI",
                  requestId,
                  params: {
                    modelId: "interactive-segmenter",
                    input: {
                      type: "bbox",
                      box: {
                        x1: Math.min(state.origin.x, event.position.x),
                        y1: Math.min(state.origin.y, event.position.y),
                        x2: Math.max(state.origin.x, event.position.x),
                        y2: Math.max(state.origin.y, event.position.y),
                      },
                    },
                  },
                },
              ],
            };
          }

          // Regular rectangle: transition to editingNew with editable preview
          return {
            newState: { phase: "editingNew", origin: state.origin, current: event.position },
            sideEffects: [
              {
                type: "updatePreview",
                preview: {
                  type: "rectangle",
                  origin: state.origin,
                  current: event.position,
                  editable: true,
                },
              },
            ],
          };
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }
        break;

      case "editingNew":
        if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
          // Compute bbox geometry from origin/current
          const x = Math.min(state.origin.x, state.current.x);
          const y = Math.min(state.origin.y, state.current.y);
          const width = Math.abs(state.current.x - state.origin.x);
          const height = Math.abs(state.current.y - state.origin.y);

          return {
            newState: { phase: "idle" },
            sideEffects: [
              { type: "updatePreview", preview: null },
              {
                type: "requestSave",
                shapeType: "bbox",
                geometry: { x, y, width, height },
              },
            ],
          };
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }

        // Ignore pointer events in editingNew — Transformer handles them
        if (
          event.type === "pointerDown" ||
          event.type === "pointerMove" ||
          event.type === "pointerUp"
        ) {
          return { newState: state, sideEffects: [] };
        }
        break;

      case "waitingForAI":
        if (event.type === "aiResult" && event.requestId === state.requestId) {
          return {
            newState: { phase: "previewingAIResult", result: event.result },
            sideEffects: [],
          };
        }
        if (event.type === "aiError" || event.type === "cancel") {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }
        break;

      case "previewingAIResult":
        if (event.type === "confirm") {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }
        if (event.type === "cancel") {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }
        break;
    }

    return { newState: state, sideEffects: [] };
  }
}
