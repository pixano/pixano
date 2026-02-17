/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/commands — Command pattern for all document mutations
// ============================================================

import type { Document, Patch } from "@pixano/document";

// Re-export Patch from document for convenience
export type { Patch } from "@pixano/document";

// --------------- Commands ---------------

/** A serializable command describing a document mutation. */
export interface Command {
  readonly type: string;
  readonly payload: unknown;
}

// --------------- Command Result ---------------

/** The result of applying a command to a document. */
export interface CommandResult {
  /** The new document snapshot after applying the command. */
  readonly newDocument: Document;
  /** The inverse command that undoes this operation. */
  readonly inverse: Command;
  /** Fine-grained patches for incremental UI updates. */
  readonly patches: ReadonlyArray<Patch>;
}

// --------------- Command Processor ---------------

/**
 * Applies commands to documents, producing new snapshots.
 * Pure function — no side effects, no framework dependencies.
 */
export interface CommandProcessor {
  apply(document: Document, command: Command): CommandResult;
}

// --------------- History ---------------

/** A single entry in the undo/redo history. */
export interface HistoryEntry {
  readonly description: string;
  readonly command: Command;
  readonly inverse: Command;
  readonly patches: ReadonlyArray<Patch>;
  readonly documentVersion: number;
}

/** An open transaction grouping multiple commands into a single undo unit. */
export interface Transaction {
  readonly description: string;
  readonly entries: ReadonlyArray<HistoryEntry>;
  readonly snapshotVersion: number;
}

/**
 * Manages undo/redo history with transaction support.
 *
 * Invariant: For every command C applied to document D:
 * apply(apply(D, C).newDocument, apply(D, C).inverse).newDocument === D
 */
export interface HistoryStack {
  readonly canUndo: boolean;
  readonly canRedo: boolean;
  readonly depth: number;
  readonly maxDepth: number;

  /** Push a completed command onto the history. Clears redo stack. */
  push(entry: HistoryEntry): void;

  /** Pop and return the most recent entry for undo. */
  undo(): HistoryEntry | undefined;

  /** Pop and return the most recent undone entry for redo. */
  redo(): HistoryEntry | undefined;

  /** Begin grouping subsequent commands into a single undo unit. */
  beginTransaction(description: string): void;

  /** Commit the open transaction as a single history entry. */
  commitTransaction(): void;

  /** Abort the open transaction, discarding all commands since begin. */
  abortTransaction(): void;

  /** Whether a transaction is currently open. */
  readonly isTransactionOpen: boolean;

  /** Clear all history. */
  clear(): void;
}
