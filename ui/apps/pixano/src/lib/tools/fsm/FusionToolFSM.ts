/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { createMergeEntities } from "$lib/commands";
import type { NodeId } from "$lib/document";

import type {
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolSideEffect,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";

/**
 * Fusion tool — merges multiple entities into one.
 *
 * States: idle → editing (collecting entities to merge) → idle
 *
 * Click entities to add/remove from the merge set.
 * Confirm to merge all selected into the first selected entity.
 */
export class FusionToolFSM implements ToolFSM {
  readonly id = "fusion";
  readonly name = "Fusion";
  readonly icon = "fusion";
  readonly defaultCursor = "default";

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  transition(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        // Fusion is triggered when entities are selected
        if (
          event.type === "confirm" ||
          (event.type === "keyDown" && event.key === "Enter")
        ) {
          if (context.selectedIds.size >= 2) {
            const ids = [...context.selectedIds] as NodeId[];
            const targetId = ids[0];
            const sourceIds = ids.slice(1);
            const sideEffects: ToolSideEffect[] = [
              {
                type: "emitCommand",
                command: createMergeEntities(targetId, sourceIds),
              },
            ];
            return { newState: { phase: "idle" }, sideEffects };
          }
        }
        break;
    }

    return { newState: state, sideEffects: [] };
  }
}
