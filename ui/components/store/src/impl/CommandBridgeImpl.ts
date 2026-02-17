/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable, type Readable } from "svelte/store";

import type { Command, CommandProcessor, HistoryEntry } from "@pixano/commands";
import { HistoryStackImpl } from "@pixano/commands";

import type { CommandBridge } from "../types";
import type { DocumentStoreImpl } from "./DocumentStoreImpl";

/**
 * Bridges the Command system to Svelte reactivity.
 *
 * Orchestrates: execute command → update document store → push to history.
 * Handles undo/redo by applying inverse commands.
 */
export class CommandBridgeImpl implements CommandBridge {
  private readonly processor: CommandProcessor;
  private readonly documentStore: DocumentStoreImpl;
  private readonly history: HistoryStackImpl;

  private readonly _canUndo = writable(false);
  private readonly _canRedo = writable(false);

  readonly canUndo: Readable<boolean> = { subscribe: this._canUndo.subscribe };
  readonly canRedo: Readable<boolean> = { subscribe: this._canRedo.subscribe };

  constructor(processor: CommandProcessor, documentStore: DocumentStoreImpl) {
    this.processor = processor;
    this.documentStore = documentStore;
    this.history = new HistoryStackImpl();
  }

  execute(command: Command): void {
    const currentDoc = this.documentStore.getCurrentDocument();
    const result = this.processor.apply(currentDoc, command);

    // Update the document store
    this.documentStore.setDocument(result.newDocument);

    // Push to history
    const entry: HistoryEntry = {
      description: command.type,
      command,
      inverse: result.inverse,
      patches: result.patches,
      documentVersion: result.newDocument.version,
    };
    this.history.push(entry);

    this.updateUndoRedoState();
  }

  undo(): void {
    const entry = this.history.undo();
    if (!entry) return;

    // Apply the inverse command
    const currentDoc = this.documentStore.getCurrentDocument();

    if (entry.inverse.type === "Composite") {
      // Composite inverse: apply all sub-commands in sequence
      const { commands } = entry.inverse.payload as { commands: Command[] };
      let doc = currentDoc;
      for (const cmd of commands) {
        const result = this.processor.apply(doc, cmd);
        doc = result.newDocument;
      }
      this.documentStore.setDocument(doc);
    } else {
      const result = this.processor.apply(currentDoc, entry.inverse);
      this.documentStore.setDocument(result.newDocument);
    }

    this.updateUndoRedoState();
  }

  redo(): void {
    const entry = this.history.redo();
    if (!entry) return;

    // Re-apply the original command
    const currentDoc = this.documentStore.getCurrentDocument();

    if (entry.command.type === "Composite") {
      const { commands } = entry.command.payload as { commands: Command[] };
      let doc = currentDoc;
      for (const cmd of commands) {
        const result = this.processor.apply(doc, cmd);
        doc = result.newDocument;
      }
      this.documentStore.setDocument(doc);
    } else {
      const result = this.processor.apply(currentDoc, entry.command);
      this.documentStore.setDocument(result.newDocument);
    }

    this.updateUndoRedoState();
  }

  beginTransaction(description: string): void {
    this.history.beginTransaction(description);
  }

  commitTransaction(): void {
    this.history.commitTransaction();
    this.updateUndoRedoState();
  }

  abortTransaction(): void {
    // Get entries from the open transaction before aborting
    const entries = this.history.getTransactionEntries();
    this.history.abortTransaction();

    // Rollback: apply inverses in reverse order
    if (entries.length > 0) {
      let doc = this.documentStore.getCurrentDocument();
      for (let i = entries.length - 1; i >= 0; i--) {
        const result = this.processor.apply(doc, entries[i].inverse);
        doc = result.newDocument;
      }
      this.documentStore.setDocument(doc);
    }

    this.updateUndoRedoState();
  }

  private updateUndoRedoState(): void {
    this._canUndo.set(this.history.canUndo);
    this._canRedo.set(this.history.canRedo);
  }
}
