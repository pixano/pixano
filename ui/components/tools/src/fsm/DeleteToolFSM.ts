/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { createDeleteAnnotation } from "@pixano/commands";

import type { ToolContext, ToolEvent, ToolFSM, ToolState, ToolTransition } from "../types";

/**
 * Delete tool — click on an annotation to delete it.
 *
 * States: idle only (stateless — each click is an immediate action).
 */
export class DeleteToolFSM implements ToolFSM {
  readonly id = "delete";
  readonly name = "Delete selection";
  readonly icon = "delete";
  readonly defaultCursor = "auto";

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  transition(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition {
    if (state.phase === "idle") {
      if (event.type === "pointerDown" && event.button === 0) {
        // Find annotation at click position (handled by canvas adapter)
        // For now, delete selected annotations
        if (context.selectedIds.size > 0) {
          const effects = [...context.selectedIds].map((id) => ({
            type: "emitCommand" as const,
            command: createDeleteAnnotation(id, true),
          }));
          return {
            newState: { phase: "idle" },
            sideEffects: effects,
          };
        }
      }

      // Delete key shortcut
      if (
        event.type === "keyDown" &&
        (event.key === "Delete" || event.key === "Backspace")
      ) {
        if (context.selectedIds.size > 0) {
          const effects = [...context.selectedIds].map((id) => ({
            type: "emitCommand" as const,
            command: createDeleteAnnotation(id, true),
          }));
          return {
            newState: { phase: "idle" },
            sideEffects: effects,
          };
        }
      }
    }

    return { newState: state, sideEffects: [] };
  }
}
