/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ToolContext, ToolEvent, ToolFSM, ToolState, ToolTransition } from "$lib/types/tools";

/**
 * Classification tool — assigns labels to the entire item/view.
 *
 * This tool is stateless from an interaction perspective.
 * Classification is handled through the inspector panel, not canvas clicks.
 */
export class ClassificationToolFSM implements ToolFSM {
  readonly id = "classification";
  readonly name = "Classification";
  readonly icon = "classification";
  readonly defaultCursor = "default";

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, _event: ToolEvent, _context: ToolContext): ToolTransition {
    // Classification doesn't have canvas interactions
    return { newState: state, sideEffects: [] };
  }
}
