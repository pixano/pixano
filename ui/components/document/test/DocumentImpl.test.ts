/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import type { NodeId, Patch } from "../src/types";
import { createBBoxAnnotationNode, createEmptyDocument, createEntityNode } from "./helpers";

describe("DocumentImpl", () => {
  // -------- Construction & Queries --------

  describe("construction & queries", () => {
    it("should return undefined for unknown node IDs", () => {
      const doc = createEmptyDocument();
      expect(doc.getNode("nonexistent" as NodeId)).toBeUndefined();
    });

    it("should return empty arrays when no nodes exist", () => {
      const doc = createEmptyDocument();
      expect(doc.getAnnotations()).toHaveLength(0);
      expect(doc.getEntities()).toHaveLength(0);
      expect(doc.getNodes()).toHaveLength(0);
    });

    it("should index annotations by view, entity, and type", () => {
      const ann1 = createBBoxAnnotationNode({ id: "ann-1" as NodeId });
      const ann2 = createBBoxAnnotationNode({
        id: "ann-2" as NodeId,
        viewRef: { id: "view-2", name: "depth" },
      });
      const entity = createEntityNode();

      const doc = createEmptyDocument().withPatches([
        { type: "add", nodeId: ann1.id, node: ann1 },
        { type: "add", nodeId: ann2.id, node: ann2 },
        { type: "add", nodeId: entity.id, node: entity },
      ]);

      expect(doc.getAnnotations()).toHaveLength(2);
      expect(doc.getEntities()).toHaveLength(1);
      expect(doc.getAnnotationsByView("image")).toHaveLength(1);
      expect(doc.getAnnotationsByView("depth")).toHaveLength(1);
      expect(doc.getAnnotationsByView("nonexistent")).toHaveLength(0);
      expect(doc.getAnnotationsByEntity("entity-1" as NodeId)).toHaveLength(2);
      expect(doc.getAnnotationsByType("BBox")).toHaveLength(2);
      expect(doc.getAnnotationsByType("Mask")).toHaveLength(0);
    });

    it("should retrieve a node by ID after adding", () => {
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument().withPatches([
        { type: "add", nodeId: ann.id, node: ann },
      ]);

      const found = doc.getNode(ann.id);
      expect(found).toBeDefined();
      expect(found?.id).toBe(ann.id);
    });
  });

  // -------- withPatches — add --------

  describe("withPatches — add", () => {
    it("should insert a node and make it appear in queries", () => {
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const newDoc = doc.withPatches([
        { type: "add", nodeId: ann.id, node: ann },
      ]);

      expect(newDoc.getNode(ann.id)).toBeDefined();
      expect(newDoc.getAnnotations()).toHaveLength(1);
      expect(newDoc.version).toBe(doc.version + 1);
    });
  });

  // -------- withPatches — remove --------

  describe("withPatches — remove", () => {
    it("should delete a node and remove it from queries", () => {
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument().withPatches([
        { type: "add", nodeId: ann.id, node: ann },
      ]);

      const newDoc = doc.withPatches([{ type: "remove", nodeId: ann.id }]);

      expect(newDoc.getNode(ann.id)).toBeUndefined();
      expect(newDoc.getAnnotations()).toHaveLength(0);
    });
  });

  // -------- withPatches — update --------

  describe("withPatches — update", () => {
    it("should merge data changes", () => {
      const ann = createBBoxAnnotationNode();
      const doc = createEmptyDocument().withPatches([
        { type: "add", nodeId: ann.id, node: ann },
      ]);

      const changes = { confidence: 0.95 };
      const newDoc = doc.withPatches([
        { type: "update", nodeId: ann.id, changes },
      ]);

      const updated = newDoc.getNode(ann.id);
      expect(updated?.data.confidence).toBe(0.95);
      // Original fields preserved
      expect(updated?.data.coords).toEqual([0.1, 0.2, 0.3, 0.4]);
    });

    it("should be a no-op for unknown node IDs", () => {
      const doc = createEmptyDocument();
      const newDoc = doc.withPatches([
        { type: "update", nodeId: "nonexistent" as NodeId, changes: { foo: "bar" } },
      ]);
      expect(newDoc.getNodes()).toHaveLength(0);
    });
  });

  // -------- Immutability --------

  describe("immutability", () => {
    it("should leave the original document unchanged after withPatches", () => {
      const doc = createEmptyDocument();
      const ann = createBBoxAnnotationNode();

      const newDoc = doc.withPatches([
        { type: "add", nodeId: ann.id, node: ann },
      ]);

      // Original unchanged
      expect(doc.getAnnotations()).toHaveLength(0);
      expect(doc.getNode(ann.id)).toBeUndefined();
      expect(doc.version).toBe(0);

      // New doc has the addition
      expect(newDoc.getAnnotations()).toHaveLength(1);
      expect(newDoc.version).toBe(1);
    });
  });

  // -------- Structural Sharing --------

  describe("structural sharing", () => {
    it("should reuse unchanged node references in the new document", () => {
      const ann1 = createBBoxAnnotationNode({ id: "ann-1" as NodeId });
      const ann2 = createBBoxAnnotationNode({ id: "ann-2" as NodeId });

      const doc = createEmptyDocument().withPatches([
        { type: "add", nodeId: ann1.id, node: ann1 },
        { type: "add", nodeId: ann2.id, node: ann2 },
      ]);

      // Update only ann1
      const newDoc = doc.withPatches([
        { type: "update", nodeId: ann1.id, changes: { confidence: 0.5 } },
      ]);

      // ann2 should be the same reference
      expect(newDoc.getNode(ann2.id)).toBe(doc.getNode(ann2.id));
      // ann1 should be a new reference
      expect(newDoc.getNode(ann1.id)).not.toBe(doc.getNode(ann1.id));
    });
  });

  // -------- Version --------

  describe("version", () => {
    it("should increment version for each withPatches call", () => {
      const doc = createEmptyDocument();
      expect(doc.version).toBe(0);

      const doc1 = doc.withPatches([]);
      expect(doc1.version).toBe(1);

      const doc2 = doc1.withPatches([]);
      expect(doc2.version).toBe(2);
    });
  });

  // -------- Multiple patches --------

  describe("multiple patches", () => {
    it("should apply multiple patches atomically", () => {
      const ann1 = createBBoxAnnotationNode({ id: "ann-1" as NodeId });
      const ann2 = createBBoxAnnotationNode({ id: "ann-2" as NodeId });
      const entity = createEntityNode();

      const patches: Patch[] = [
        { type: "add", nodeId: ann1.id, node: ann1 },
        { type: "add", nodeId: ann2.id, node: ann2 },
        { type: "add", nodeId: entity.id, node: entity },
      ];

      const doc = createEmptyDocument().withPatches(patches);

      expect(doc.getAnnotations()).toHaveLength(2);
      expect(doc.getEntities()).toHaveLength(1);
      expect(doc.getNodes()).toHaveLength(3);
    });
  });
});
