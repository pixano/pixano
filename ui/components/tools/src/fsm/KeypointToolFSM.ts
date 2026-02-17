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
 * Keypoint tool — place keypoints one by one according to a template.
 *
 * States: idle → placingKeypoints → idle
 *
 * Each click places a keypoint. After all template points are placed,
 * the annotation is committed.
 */
export class KeypointToolFSM implements ToolFSM {
  readonly id = "keypoint";
  readonly name = "Keypoint";
  readonly icon = "keypoint";
  readonly defaultCursor = "crosshair";

  /** Number of keypoints expected (from template). 0 = unlimited. */
  private expectedCount: number = 0;

  setExpectedCount(count: number): void {
    this.expectedCount = count;
  }

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, _context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          const points = [event.position];
          const sideEffects: ToolSideEffect[] = [
            { type: "beginTransaction", description: "Place keypoints" },
            { type: "updatePreview", preview: { type: "keypoints", points } },
          ];

          if (this.expectedCount === 1) {
            // Single keypoint → confirm immediately
            sideEffects.push({ type: "commitTransaction" });
            sideEffects.push({ type: "updatePreview", preview: null });
            return { newState: { phase: "idle" }, sideEffects };
          }

          return {
            newState: { phase: "placingKeypoints", points, current: event.position },
            sideEffects,
          };
        }
        break;

      case "placingKeypoints": {
        const points = state.points;

        if (event.type === "pointerDown" && event.button === 0) {
          const newPoints = [...points, event.position];
          const sideEffects: ToolSideEffect[] = [
            { type: "updatePreview", preview: { type: "keypoints", points: newPoints } },
          ];

          // Check if all keypoints placed
          if (this.expectedCount > 0 && newPoints.length >= this.expectedCount) {
            sideEffects.push({ type: "commitTransaction" });
            sideEffects.push({ type: "updatePreview", preview: null });
            return { newState: { phase: "idle" }, sideEffects };
          }

          return {
            newState: { phase: "placingKeypoints", points: newPoints, current: event.position },
            sideEffects,
          };
        }

        if (event.type === "pointerMove") {
          return {
            newState: { phase: "placingKeypoints", points, current: event.position },
            sideEffects: [],
          };
        }

        if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
          if (points.length > 0) {
            return {
              newState: { phase: "idle" },
              sideEffects: [
                { type: "updatePreview", preview: null },
                { type: "commitTransaction" },
              ],
            };
          }
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
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
