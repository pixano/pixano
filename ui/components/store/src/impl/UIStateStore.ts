/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { derived, writable, type Readable, type Writable } from "svelte/store";

import type { NodeId } from "@pixano/document";

// --------------- UI State Types ---------------

/** Display control for an individual node (annotation or entity). */
export interface DisplayControl {
  hidden: boolean;
  editing: boolean;
  highlighted: "all" | "self" | "none";
  open?: boolean;
}

export const DEFAULT_DISPLAY_CONTROL: DisplayControl = {
  hidden: false,
  editing: false,
  highlighted: "all",
};

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
  private readonly _states: Writable<Map<NodeId, NodeUIState>>;
  readonly states: Readable<Map<NodeId, NodeUIState>>;

  constructor() {
    this._states = writable<Map<NodeId, NodeUIState>>(new Map());
    this.states = { subscribe: this._states.subscribe };
  }

  /** Get UI state for a node, with defaults if not yet set. */
  getState(nodeId: NodeId): NodeUIState {
    let current: Map<NodeId, NodeUIState> | undefined;
    this._states.subscribe((s) => (current = s))();
    return current?.get(nodeId) ?? { displayControl: { ...DEFAULT_DISPLAY_CONTROL } };
  }

  /** Update UI state for a node. */
  setState(nodeId: NodeId, state: Partial<NodeUIState>): void {
    this._states.update((map) => {
      const existing = map.get(nodeId) ?? {
        displayControl: { ...DEFAULT_DISPLAY_CONTROL },
      };
      map.set(nodeId, { ...existing, ...state });
      return new Map(map);
    });
  }

  /** Update display control for a node. */
  setDisplayControl(nodeId: NodeId, control: Partial<DisplayControl>): void {
    this._states.update((map) => {
      const existing = map.get(nodeId) ?? {
        displayControl: { ...DEFAULT_DISPLAY_CONTROL },
      };
      map.set(nodeId, {
        ...existing,
        displayControl: { ...existing.displayControl, ...control },
      });
      return new Map(map);
    });
  }

  /** Derived store for a specific node's display control. */
  displayControlFor(nodeId: NodeId): Readable<DisplayControl> {
    return derived(this._states, ($states) => {
      return $states.get(nodeId)?.displayControl ?? DEFAULT_DISPLAY_CONTROL;
    });
  }

  /** Clear highlighting for all nodes. */
  clearAllHighlighting(): void {
    this._states.update((map) => {
      for (const [id, state] of map) {
        map.set(id, {
          ...state,
          displayControl: { ...state.displayControl, highlighted: "none" },
        });
      }
      return new Map(map);
    });
  }

  /** Remove UI state for deleted nodes. */
  removeNode(nodeId: NodeId): void {
    this._states.update((map) => {
      map.delete(nodeId);
      return new Map(map);
    });
  }

  /** Clear all UI state. */
  clear(): void {
    this._states.set(new Map());
  }
}
