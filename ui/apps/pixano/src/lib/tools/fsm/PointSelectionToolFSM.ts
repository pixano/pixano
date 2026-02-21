/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  LabeledClick,
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";

/**
 * Point selection tool — for SAM-like interactive segmentation.
 *
 * States: idle → collectingPoints → waitingForAI → previewingAIResult → idle
 *
 * Each click adds a labeled point (+/-). After each click, an AI request
 * is sent with all collected points. Results can be accepted or rejected.
 */
export class PointSelectionToolFSM implements ToolFSM {
  readonly id = "point-selection";
  readonly name = "Point selection";
  readonly icon = "point";
  readonly defaultCursor = "crosshair";

  /** Current label: 1 = positive, 0 = negative */
  private label: number = 1;

  setLabel(label: number): void {
    this.label = label;
  }

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, _context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          const click: LabeledClick = { point: event.position, label: this.label };
          const requestId = `point-sel-${Date.now()}`;
          return {
            newState: { phase: "collectingPoints", points: [click] },
            sideEffects: [
              {
                type: "updatePreview",
                preview: { type: "point", position: event.position, label: this.label },
              },
              {
                type: "requestAI",
                requestId,
                params: {
                  modelId: "interactive-segmenter",
                  input: { type: "points", clicks: [click] },
                },
              },
            ],
          };
        }
        break;

      case "collectingPoints": {
        const existingPoints = state.points;

        if (event.type === "pointerDown" && event.button === 0) {
          const click: LabeledClick = { point: event.position, label: this.label };
          const newPoints = [...existingPoints, click];
          const requestId = `point-sel-${Date.now()}`;
          return {
            newState: { phase: "collectingPoints", points: newPoints },
            sideEffects: [
              {
                type: "requestAI",
                requestId,
                params: {
                  modelId: "interactive-segmenter",
                  input: { type: "points", clicks: newPoints },
                },
              },
            ],
          };
        }

        if (event.type === "aiResult") {
          return {
            newState: { phase: "previewingAIResult", result: event.result },
            sideEffects: [],
          };
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }
        break;
      }

      case "previewingAIResult":
        // Allow adding more points to refine
        if (event.type === "pointerDown" && event.button === 0) {
          const click: LabeledClick = { point: event.position, label: this.label };
          const requestId = `point-sel-${Date.now()}`;
          return {
            newState: { phase: "collectingPoints", points: [click] },
            sideEffects: [
              {
                type: "requestAI",
                requestId,
                params: {
                  modelId: "interactive-segmenter",
                  input: { type: "points", clicks: [click] },
                },
              },
            ],
          };
        }

        if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
          // Accept the AI result as an annotation
          return {
            newState: { phase: "idle" },
            sideEffects: [{ type: "updatePreview", preview: null }],
          };
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
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
