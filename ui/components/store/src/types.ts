/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/store — Bridges core state <-> Svelte reactivity
// ============================================================

import type { Readable, Writable } from "svelte/store";

import type { AnnotationNode, Document, NodeId } from "@pixano/document";
import type { PreviewShape, ToolFSM, ToolState } from "@pixano/tools";

// --------------- Document Store ---------------

/**
 * Reactive Svelte store exposing the Document model.
 *
 * Provides derived stores for filtered views of annotations, entities, etc.
 * All mutations go through CommandBridge — these stores are read-only.
 */
export interface DocumentStore {
  /** The current document snapshot. */
  readonly document: Readable<Document>;

  /** All annotations in the document. */
  readonly annotations: Readable<ReadonlyArray<AnnotationNode>>;

  /** Annotations filtered by view name. */
  annotationsByView(viewName: string): Readable<ReadonlyArray<AnnotationNode>>;

  /** Currently selected node IDs. */
  readonly selectedIds: Writable<Set<NodeId>>;
}

// --------------- Command Bridge ---------------

/**
 * Bridges the command system to Svelte stores.
 *
 * Executes commands, manages history, and updates the DocumentStore reactively.
 */
export interface CommandBridge {
  /** Execute a command and push to history. */
  execute(command: import("@pixano/commands").Command): void;

  /** Undo the last command. */
  undo(): void;

  /** Redo the last undone command. */
  redo(): void;

  /** Whether undo is available. */
  readonly canUndo: Readable<boolean>;

  /** Whether redo is available. */
  readonly canRedo: Readable<boolean>;

  /** Begin a transaction (groups commands into one undo unit). */
  beginTransaction(description: string): void;

  /** Commit the current transaction. */
  commitTransaction(): void;

  /** Abort the current transaction (rolls back). */
  abortTransaction(): void;
}

// --------------- Tool Bridge ---------------

/**
 * Bridges tool FSMs to Svelte reactivity.
 *
 * Manages active tool selection, state transitions, and preview rendering.
 */
export interface ToolBridge {
  /** The currently active tool FSM. */
  readonly activeTool: Writable<ToolFSM>;

  /** The current state of the active tool. */
  readonly toolState: Readable<ToolState>;

  /** The current preview shape (transient, not in document). */
  readonly preview: Readable<PreviewShape | null>;

  /** Dispatch an event to the active tool FSM. */
  dispatchEvent(event: import("@pixano/tools").ToolEvent): void;

  /** Set canvas context used to build ToolContext for FSM transitions. */
  setCanvasContext(viewName: string, canvasWidth: number, canvasHeight: number): void;

  /** Register a callback for requestSave side effects. */
  onRequestSave(
    callback: (shapeType: "bbox" | "polygon" | "mask" | "keypoints", geometry: unknown) => void,
  ): void;

  /** Switch the active FSM and reset transient state. */
  switchTool(tool: ToolFSM): void;
}
