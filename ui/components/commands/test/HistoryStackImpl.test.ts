/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { HistoryEntry } from "../src/types";
import { HistoryStackImpl } from "../src/impl/HistoryStackImpl";

function createEntry(description: string, version = 1): HistoryEntry {
  return {
    description,
    command: { type: "TestCommand", payload: { description } },
    inverse: { type: "TestInverse", payload: { description } },
    patches: [],
    documentVersion: version,
  };
}

describe("HistoryStackImpl", () => {
  // -------- Basic Operations --------

  describe("basic operations", () => {
    it("should start with empty stacks", () => {
      const stack = new HistoryStackImpl();
      expect(stack.canUndo).toBe(false);
      expect(stack.canRedo).toBe(false);
      expect(stack.depth).toBe(0);
    });

    it("should push and undo", () => {
      const stack = new HistoryStackImpl();
      const entry = createEntry("add rect");

      stack.push(entry);
      expect(stack.canUndo).toBe(true);
      expect(stack.canRedo).toBe(false);
      expect(stack.depth).toBe(1);

      const undone = stack.undo();
      expect(undone).toBe(entry);
      expect(stack.canUndo).toBe(false);
      expect(stack.canRedo).toBe(true);
    });

    it("should redo after undo", () => {
      const stack = new HistoryStackImpl();
      const entry = createEntry("add rect");

      stack.push(entry);
      stack.undo();

      const redone = stack.redo();
      expect(redone).toBe(entry);
      expect(stack.canUndo).toBe(true);
      expect(stack.canRedo).toBe(false);
    });

    it("should return undefined when undoing empty stack", () => {
      const stack = new HistoryStackImpl();
      expect(stack.undo()).toBeUndefined();
    });

    it("should return undefined when redoing empty stack", () => {
      const stack = new HistoryStackImpl();
      expect(stack.redo()).toBeUndefined();
    });
  });

  // -------- Max Depth --------

  describe("max depth", () => {
    it("should evict oldest entries beyond maxDepth", () => {
      const stack = new HistoryStackImpl(3);

      stack.push(createEntry("e1", 1));
      stack.push(createEntry("e2", 2));
      stack.push(createEntry("e3", 3));
      expect(stack.depth).toBe(3);

      stack.push(createEntry("e4", 4));
      expect(stack.depth).toBe(3);

      // The first entry (e1) was evicted, so undo 3 times gives e4, e3, e2
      const u1 = stack.undo();
      expect(u1?.description).toBe("e4");
      const u2 = stack.undo();
      expect(u2?.description).toBe("e3");
      const u3 = stack.undo();
      expect(u3?.description).toBe("e2");
      expect(stack.undo()).toBeUndefined();
    });
  });

  // -------- Redo Clearing --------

  describe("redo clearing", () => {
    it("should clear redo stack when a new command is pushed after undo", () => {
      const stack = new HistoryStackImpl();

      stack.push(createEntry("e1"));
      stack.push(createEntry("e2"));
      stack.undo(); // undo e2
      expect(stack.canRedo).toBe(true);

      stack.push(createEntry("e3"));
      expect(stack.canRedo).toBe(false);
      expect(stack.depth).toBe(2); // e1, e3
    });
  });

  // -------- Transactions --------

  describe("transactions", () => {
    it("should collapse transaction entries into a single composite entry", () => {
      const stack = new HistoryStackImpl();

      stack.beginTransaction("batch move");
      stack.push(createEntry("move-1", 1));
      stack.push(createEntry("move-2", 2));
      stack.push(createEntry("move-3", 3));
      stack.commitTransaction();

      expect(stack.depth).toBe(1);
      const entry = stack.undo();
      expect(entry?.description).toBe("batch move");
      expect(entry?.command.type).toBe("Composite");
    });

    it("should discard entries when transaction is aborted", () => {
      const stack = new HistoryStackImpl();

      stack.push(createEntry("before"));
      stack.beginTransaction("batch");
      stack.push(createEntry("inside-1"));
      stack.push(createEntry("inside-2"));
      stack.abortTransaction();

      // Only the entry before the transaction remains
      expect(stack.depth).toBe(1);
      expect(stack.isTransactionOpen).toBe(false);
    });

    it("should handle empty transaction commit", () => {
      const stack = new HistoryStackImpl();
      stack.beginTransaction("empty");
      stack.commitTransaction();
      expect(stack.depth).toBe(0);
    });

    it("should throw on nested transactions", () => {
      const stack = new HistoryStackImpl();
      stack.beginTransaction("outer");
      expect(() => stack.beginTransaction("inner")).toThrow();
    });

    it("should throw when committing without an open transaction", () => {
      const stack = new HistoryStackImpl();
      expect(() => stack.commitTransaction()).toThrow();
    });

    it("should throw when aborting without an open transaction", () => {
      const stack = new HistoryStackImpl();
      expect(() => stack.abortTransaction()).toThrow();
    });

    it("should not allow undo/redo during an open transaction", () => {
      const stack = new HistoryStackImpl();
      stack.push(createEntry("e1"));
      stack.beginTransaction("batch");
      expect(stack.undo()).toBeUndefined();
      expect(stack.redo()).toBeUndefined();
      stack.abortTransaction();
    });

    it("should report isTransactionOpen correctly", () => {
      const stack = new HistoryStackImpl();
      expect(stack.isTransactionOpen).toBe(false);
      stack.beginTransaction("test");
      expect(stack.isTransactionOpen).toBe(true);
      stack.commitTransaction();
      expect(stack.isTransactionOpen).toBe(false);
    });
  });

  // -------- Clear --------

  describe("clear", () => {
    it("should clear all history", () => {
      const stack = new HistoryStackImpl();
      stack.push(createEntry("e1"));
      stack.push(createEntry("e2"));
      stack.undo();
      stack.clear();

      expect(stack.canUndo).toBe(false);
      expect(stack.canRedo).toBe(false);
      expect(stack.depth).toBe(0);
    });
  });
});
