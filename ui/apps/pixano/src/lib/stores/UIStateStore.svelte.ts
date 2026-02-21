/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { NodeId } from "$lib/document";

import { initDisplayControl, type DisplayControl } from "$lib/types/dataset";
import type { ReactiveReadonly } from "$lib/types/store";

// --------------- UI State Types ---------------

export type { DisplayControl };

export const DEFAULT_DISPLAY_CONTROL: DisplayControl = initDisplayControl;

/** Per-node UI state — separated from the domain Document model. */
export interface NodeUIState {
  displayControl: DisplayControl;
  reviewState?: "accepted" | "rejected";
}

// --------------- UI State Store ---------------

/**
 * Manages per-node UI state (display control, highlighting, etc.)
 * that is NOT part of the domain document model.
 *
 * This cleanly separates UI concerns from the annotation data.
 */
export class UIStateStore {
  private _states = $state<Map<NodeId, NodeUIState>>(new Map());

  readonly states: ReactiveReadonly<Map<NodeId, NodeUIState>>;

  constructor() {
    const self = this;
    this.states = {
      get value() { return self._states; },
    };
  }

  /** Get UI state for a node, with defaults if not yet set. */
  getState(nodeId: NodeId): NodeUIState {
    return this._states.get(nodeId) ?? { displayControl: { ...DEFAULT_DISPLAY_CONTROL } };
  }

  /** Update UI state for a node. */
  setState(nodeId: NodeId, state: Partial<NodeUIState>): void {
    const existing = this._states.get(nodeId) ?? {
      displayControl: { ...DEFAULT_DISPLAY_CONTROL },
    };
    const newMap = new Map(this._states);
    newMap.set(nodeId, { ...existing, ...state });
    this._states = newMap;
  }

  /** Update display control for a node. */
  setDisplayControl(nodeId: NodeId, control: Partial<DisplayControl>): void {
    const existing = this._states.get(nodeId) ?? {
      displayControl: { ...DEFAULT_DISPLAY_CONTROL },
    };
    const newMap = new Map(this._states);
    newMap.set(nodeId, {
      ...existing,
      displayControl: { ...existing.displayControl, ...control },
    });
    this._states = newMap;
  }

  /** Getter for a specific node's display control. */
  displayControlFor(nodeId: NodeId): ReactiveReadonly<DisplayControl> {
    const self = this;
    return {
      get value() {
        return self._states.get(nodeId)?.displayControl ?? DEFAULT_DISPLAY_CONTROL;
      },
    };
  }

  /** Clear highlighting for all nodes. */
  clearAllHighlighting(): void {
    const newMap = new Map(this._states);
    for (const [id, state] of newMap) {
      newMap.set(id, {
        ...state,
        displayControl: { ...state.displayControl, highlighted: "none" },
      });
    }
    this._states = newMap;
  }

  /** Remove UI state for deleted nodes. */
  removeNode(nodeId: NodeId): void {
    const newMap = new Map(this._states);
    newMap.delete(nodeId);
    this._states = newMap;
  }

  /** Clear all UI state. */
  clear(): void {
    this._states = new Map();
  }
}
