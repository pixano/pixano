/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/store — Bridges core state <-> Svelte reactivity
// ============================================================

import type { AnnotationNode, Document, NodeId } from "$lib/document";
import type { AIRequestParams, PreviewShape, ToolFSM, ToolState } from "$lib/tools";

/** Cleanup callback. */
export type Unsubscribe = () => void;

/** A reactive read-only value. */
export interface ReactiveReadonly<T> {
  readonly value: T;
}

/** A reactive read-write value. */
export interface ReactiveValue<T> {
  value: T;
  update(fn: (prev: T) => T): void;
}

// --------------- Document Store ---------------

/**
 * Reactive store exposing the Document model.
 *
 * Provides derived getters for filtered views of annotations, entities, etc.
 * All mutations go through CommandBridge — these stores are read-only.
 */
export interface DocumentStore {
  /** The current document snapshot. */
  readonly document: ReactiveReadonly<Document>;

  /** All annotations in the document. */
  readonly annotations: ReactiveReadonly<ReadonlyArray<AnnotationNode>>;

  /** Annotations filtered by view name. */
  annotationsByView(viewName: string): ReactiveReadonly<ReadonlyArray<AnnotationNode>>;

  /** Currently selected node IDs. */
  readonly selectedIds: ReactiveValue<Set<NodeId>>;
}

// --------------- Command Bridge ---------------

/**
 * Bridges the command system to reactive stores.
 *
 * Executes commands, manages history, and updates the DocumentStore reactively.
 */
export interface CommandBridge {
  /** Execute a command and push to history. */
  execute(command: import("$lib/commands").Command): void;

  /** Undo the last command. */
  undo(): void;

  /** Redo the last undone command. */
  redo(): void;

  /** Whether undo is available. */
  readonly canUndo: ReactiveReadonly<boolean>;

  /** Whether redo is available. */
  readonly canRedo: ReactiveReadonly<boolean>;

  /** Begin a transaction (groups commands into one undo unit). */
  beginTransaction(description: string): void;

  /** Commit the current transaction. */
  commitTransaction(): void;

  /** Abort the current transaction (rolls back). */
  abortTransaction(): void;
}

// --------------- Tool Bridge ---------------

/**
 * Bridges tool FSMs to reactivity.
 *
 * Manages active tool selection, state transitions, and preview rendering.
 */
export interface ToolBridge {
  /** The currently active tool FSM. */
  readonly activeTool: ReactiveValue<ToolFSM>;

  /** The current state of the active tool. */
  readonly toolState: ReactiveReadonly<ToolState>;

  /** The current preview shape (transient, not in document). */
  readonly preview: ReactiveReadonly<PreviewShape | null>;

  /** Dispatch an event to the active tool FSM. */
  dispatchEvent(event: import("$lib/tools").ToolEvent): void;

  /** Set canvas context used to build ToolContext for FSM transitions. */
  setCanvasContext(viewName: string, viewId: string, canvasWidth: number, canvasHeight: number): void;

  /** Register a callback for requestSave side effects. */
  onRequestSave(
    callback: (
      shapeType: "bbox" | "polygon" | "polyline" | "mask" | "keypoints",
      geometry: unknown,
    ) => void,
  ): void;

  /** Register a callback for AI prompt and confirmation requests. */
  onAIRequest(callback: (requestId: string, params: AIRequestParams) => void): void;

  /** Switch the active FSM and reset transient state. */
  switchTool(tool: ToolFSM): void;
}
