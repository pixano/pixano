/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationNode, DocumentNode, EntityNode, NodeId } from "../src/types";
import { DocumentImpl } from "../src/impl/DocumentImpl";

/** Create a minimal empty document for testing. */
export function createEmptyDocument(id = "test-doc"): DocumentImpl {
  const item: DocumentNode = {
    id: "item-1" as NodeId,
    nodeType: "item",
    tableInfo: { name: "item", group: "item", base_schema: "Item" },
    data: {},
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
  };

  return new DocumentImpl({
    id,
    item,
    nodes: new Map(),
    relations: [],
    coordinateFrames: new Map(),
    timelines: new Map(),
    version: 0,
  });
}

/** Create a test BBox annotation node. */
export function createBBoxAnnotationNode(
  overrides?: Partial<AnnotationNode>,
): AnnotationNode {
  const now = "2024-01-01T00:00:00Z";
  return {
    id: (overrides?.id ?? "ann-1") as NodeId,
    nodeType: "annotation",
    tableInfo: { name: "bbox", group: "annotations", base_schema: "BBox" },
    data: {
      coords: [0.1, 0.2, 0.3, 0.4],
      format: "xywh",
      is_normalized: true,
      confidence: -1,
    },
    createdAt: now,
    updatedAt: now,
    itemRef: { id: "item-1", name: "item" },
    viewRef: { id: "view-1", name: "image" },
    entityRef: { id: "entity-1", name: "" },
    sourceRef: { id: "", name: "" },
    ...overrides,
  };
}

/** Create a test entity node. */
export function createEntityNode(
  overrides?: Partial<EntityNode>,
): EntityNode {
  const now = "2024-01-01T00:00:00Z";
  return {
    id: (overrides?.id ?? "entity-1") as NodeId,
    nodeType: "entity",
    tableInfo: { name: "entity", group: "entities", base_schema: "Entity" },
    data: {},
    createdAt: now,
    updatedAt: now,
    itemRef: { id: "item-1", name: "item" },
    ...overrides,
  };
}
