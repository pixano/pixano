/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Command, HistoryEntry, HistoryStack, Patch } from "$lib/types/commands";

const DEFAULT_MAX_DEPTH = 100;

/**
 * HistoryStack with undo/redo and transaction support.
 *
 * Transactions group multiple commands into a single undo unit.
 * When a transaction is committed, all its entries are collapsed
 * into a single composite HistoryEntry.
 */
export class HistoryStackImpl implements HistoryStack {
  private undoStack: HistoryEntry[] = [];
  private redoStack: HistoryEntry[] = [];
  private openTransaction: {
    description: string;
    entries: HistoryEntry[];
    snapshotVersion: number;
  } | null = null;

  readonly maxDepth: number;

  constructor(maxDepth: number = DEFAULT_MAX_DEPTH) {
    this.maxDepth = maxDepth;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  get depth(): number {
    return this.undoStack.length;
  }

  get isTransactionOpen(): boolean {
    return this.openTransaction !== null;
  }

  push(entry: HistoryEntry): void {
    if (this.openTransaction) {
      this.openTransaction.entries.push(entry);
      return;
    }

    this.undoStack.push(entry);
    // Clear redo stack on new action (standard undo/redo behavior)
    this.redoStack = [];

    // Enforce max depth
    while (this.undoStack.length > this.maxDepth) {
      this.undoStack.shift();
    }
  }

  undo(): HistoryEntry | undefined {
    if (this.openTransaction) {
      // Cannot undo while a transaction is open
      return undefined;
    }
    const entry = this.undoStack.pop();
    if (entry) {
      this.redoStack.push(entry);
    }
    return entry;
  }

  redo(): HistoryEntry | undefined {
    if (this.openTransaction) {
      return undefined;
    }
    const entry = this.redoStack.pop();
    if (entry) {
      this.undoStack.push(entry);
    }
    return entry;
  }

  beginTransaction(description: string): void {
    if (this.openTransaction) {
      throw new Error(
        `Transaction already open: "${this.openTransaction.description}". ` +
          `Nested transactions are not supported.`,
      );
    }
    this.openTransaction = {
      description,
      entries: [],
      snapshotVersion: 0, // Will be set from the first entry
    };
  }

  commitTransaction(): void {
    if (!this.openTransaction) {
      throw new Error("No transaction to commit");
    }

    const { description, entries } = this.openTransaction;
    this.openTransaction = null;

    if (entries.length === 0) {
      return; // Empty transaction, nothing to push
    }

    // Collapse all entries into a single composite entry
    // The composite command chains all individual commands
    // The composite inverse chains all individual inverses in reverse order
    const compositeCommand: Command = {
      type: "Composite",
      payload: { commands: entries.map((e) => e.command) },
    };

    const compositeInverse: Command = {
      type: "Composite",
      payload: { commands: entries.map((e) => e.inverse).reverse() },
    };

    const allPatches: Patch[] = entries.flatMap((e) => [...e.patches]);

    const compositeEntry: HistoryEntry = {
      description,
      command: compositeCommand,
      inverse: compositeInverse,
      patches: allPatches,
      documentVersion: entries[entries.length - 1].documentVersion,
    };

    this.push(compositeEntry);
  }

  abortTransaction(): void {
    if (!this.openTransaction) {
      throw new Error("No transaction to abort");
    }

    this.openTransaction = null;
    // The caller (CommandBridge) is responsible for reverting the document
    // using getTransactionEntries() before calling abortTransaction().
  }

  /** Get the entries from the current open transaction (for abort rollback). */
  getTransactionEntries(): ReadonlyArray<HistoryEntry> {
    return this.openTransaction?.entries ?? [];
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
    this.openTransaction = null;
  }
}
