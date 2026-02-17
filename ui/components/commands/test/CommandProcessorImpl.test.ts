/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { NodeId } from "@pixano/document";
import {
  createBBoxAnnotationNode,
  createEmptyDocument,
  createEntityNode,
} from "@pixano/document/test/helpers";

import { CommandProcessorImpl } from "../src/impl/CommandProcessorImpl";
import {
  createAddAnnotation,
  createDeleteAnnotation,
  createUpdateAnnotation,
} from "../src/commands/annotationCommands";

describe("CommandProcessorImpl", () => {
  // -------- AddAnnotation --------

  describe("AddAnnotation", () => {
    it("should add a node to the document", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const result = processor.apply(doc, createAddAnnotation(ann));

      expect(result.newDocument.getNode(ann.id)).toBeDefined();
      expect(result.newDocument.getAnnotations()).toHaveLength(1);
      expect(result.patches).toHaveLength(1);
      expect(result.patches[0].type).toBe("add");
    });

    it("should produce DeleteAnnotation as inverse", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const result = processor.apply(doc, createAddAnnotation(ann));

      expect(result.inverse.type).toBe("DeleteAnnotation");
    });

    it("should update annotation indexes", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const result = processor.apply(doc, createAddAnnotation(ann));
      const newDoc = result.newDocument;

      expect(newDoc.getAnnotationsByView("image")).toHaveLength(1);
      expect(newDoc.getAnnotationsByEntity("entity-1" as NodeId)).toHaveLength(1);
      expect(newDoc.getAnnotationsByType("BBox")).toHaveLength(1);
    });
  });

  // -------- DeleteAnnotation --------

  describe("DeleteAnnotation", () => {
    it("should remove a node from the document", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const deleteResult = processor.apply(
        addResult.newDocument,
        createDeleteAnnotation(ann.id, false),
      );

      expect(deleteResult.newDocument.getNode(ann.id)).toBeUndefined();
      expect(deleteResult.newDocument.getAnnotations()).toHaveLength(0);
    });

    it("should produce BatchAdd as inverse", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const deleteResult = processor.apply(
        addResult.newDocument,
        createDeleteAnnotation(ann.id, false),
      );

      expect(deleteResult.inverse.type).toBe("BatchAdd");
    });

    it("should cascade delete orphaned entity", () => {
      const processor = new CommandProcessorImpl();
      const entity = createEntityNode({ id: "entity-1" as NodeId });
      const ann = createBBoxAnnotationNode({
        id: "ann-1" as NodeId,
        entityRef: { id: "entity-1", name: "" },
      });
      const doc = createEmptyDocument();

      // Add entity and annotation
      let result = processor.apply(doc, { type: "BatchAdd", payload: { nodes: [entity, ann] } });

      // Delete with cascade
      result = processor.apply(
        result.newDocument,
        createDeleteAnnotation(ann.id, true),
      );

      expect(result.newDocument.getNode(ann.id)).toBeUndefined();
      expect(result.newDocument.getNode(entity.id)).toBeUndefined();
    });

    it("should be a no-op for nonexistent nodes", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();

      const result = processor.apply(doc, createDeleteAnnotation("nonexistent" as NodeId, false));

      expect(result.newDocument.getAnnotations()).toHaveLength(0);
      expect(result.inverse.type).toBe("Noop");
    });
  });

  // -------- UpdateAnnotation --------

  describe("UpdateAnnotation", () => {
    it("should merge data fields", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const updateResult = processor.apply(
        addResult.newDocument,
        createUpdateAnnotation(ann.id, { confidence: 0.95 }),
      );

      const updated = updateResult.newDocument.getNode(ann.id);
      expect(updated?.data.confidence).toBe(0.95);
      expect(updated?.data.coords).toEqual([0.1, 0.2, 0.3, 0.4]);
    });

    it("should produce inverse that restores old values", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const updateResult = processor.apply(
        addResult.newDocument,
        createUpdateAnnotation(ann.id, { confidence: 0.95 }),
      );

      expect(updateResult.inverse.type).toBe("UpdateAnnotation");
      const inversePayload = updateResult.inverse.payload as { changes: Record<string, unknown> };
      expect(inversePayload.changes.confidence).toBe(-1);
    });
  });

  // -------- Undo Roundtrip --------

  describe("undo roundtrip", () => {
    it("should roundtrip AddAnnotation: apply → inverse ≡ original", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const result = processor.apply(doc, createAddAnnotation(ann));
      const undone = processor.apply(result.newDocument, result.inverse);

      expect(undone.newDocument.getNode(ann.id)).toBeUndefined();
      expect(undone.newDocument.getAnnotations()).toHaveLength(0);
    });

    it("should roundtrip UpdateAnnotation: apply → inverse ≡ original", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const updateResult = processor.apply(
        addResult.newDocument,
        createUpdateAnnotation(ann.id, { confidence: 0.95 }),
      );
      const undone = processor.apply(updateResult.newDocument, updateResult.inverse);

      expect(undone.newDocument.getNode(ann.id)?.data.confidence).toBe(-1);
    });

    it("should roundtrip DeleteAnnotation: apply → inverse ≡ original", () => {
      const processor = new CommandProcessorImpl();
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument();

      const addResult = processor.apply(doc, createAddAnnotation(ann));
      const deleteResult = processor.apply(
        addResult.newDocument,
        createDeleteAnnotation(ann.id, false),
      );
      const undone = processor.apply(deleteResult.newDocument, deleteResult.inverse);

      expect(undone.newDocument.getNode(ann.id)).toBeDefined();
      expect(undone.newDocument.getAnnotations()).toHaveLength(1);
    });
  });

  // -------- Unknown Command --------

  describe("unknown command", () => {
    it("should throw for unregistered command types", () => {
      const processor = new CommandProcessorImpl();
      const doc = createEmptyDocument();

      expect(() =>
        processor.apply(doc, { type: "SomethingUnknown", payload: {} }),
      ).toThrow("Unknown command type: SomethingUnknown");
    });
  });
});
