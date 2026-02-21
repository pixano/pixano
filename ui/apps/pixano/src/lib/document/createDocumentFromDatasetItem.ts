/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DocumentImpl } from "./DocumentImpl";
import type {
  AnnotationNode,
  CoordinateFrame,
  DocumentNode,
  EntityNode,
  NodeId,
  Relation,
  TableInfo,
  Timeline,
  TimelineRange,
} from "$lib/types/document";

// --------------- DatasetItem shape (from @pixano/core) ---------------
// We define a minimal structural type here so @pixano/document stays
// framework-agnostic and doesn't import @pixano/core directly.

interface DatasetItemRef {
  id: string;
  name: string;
}

interface DatasetItemBaseData {
  id: string;
  table_info: { name: string; group: string; base_schema: string };
  created_at: string;
  updated_at: string;
  data: Record<string, unknown>;
}

interface DatasetItemShape {
  item: DatasetItemBaseData;
  entities: Record<string, DatasetItemBaseData | DatasetItemBaseData[]>;
  annotations: Record<string, DatasetItemBaseData[]>;
  views: Record<string, DatasetItemBaseData | DatasetItemBaseData[]>;
}

// --------------- Helper functions ---------------

function toNodeId(id: string): NodeId {
  return id as NodeId;
}

function toTableInfo(raw: { name: string; group: string; base_schema: string }): TableInfo {
  return { name: raw.name, group: raw.group, base_schema: raw.base_schema };
}

function extractRef(data: Record<string, unknown>, refKey: string): DatasetItemRef {
  const ref = data[refKey] as DatasetItemRef | undefined;
  return ref ?? { id: "", name: "" };
}

function makeItemNode(raw: DatasetItemBaseData): DocumentNode {
  return {
    id: toNodeId(raw.id),
    nodeType: "item",
    tableInfo: toTableInfo(raw.table_info),
    data: raw.data,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function makeAnnotationNode(raw: DatasetItemBaseData): AnnotationNode {
  return {
    id: toNodeId(raw.id),
    nodeType: "annotation",
    tableInfo: toTableInfo(raw.table_info),
    data: raw.data,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    itemRef: extractRef(raw.data, "item_ref"),
    viewRef: extractRef(raw.data, "view_ref"),
    entityRef: extractRef(raw.data, "entity_ref"),
    sourceRef: extractRef(raw.data, "source_ref"),
  };
}

function makeEntityNode(raw: DatasetItemBaseData): EntityNode {
  const parentRef = extractRef(raw.data, "parent_ref");
  return {
    id: toNodeId(raw.id),
    nodeType: "entity",
    tableInfo: toTableInfo(raw.table_info),
    data: raw.data,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    itemRef: extractRef(raw.data, "item_ref"),
    parentRef: parentRef.id ? parentRef : undefined,
  };
}

function makeViewNode(raw: DatasetItemBaseData): DocumentNode {
  return {
    id: toNodeId(raw.id),
    nodeType: "view",
    tableInfo: toTableInfo(raw.table_info),
    data: raw.data,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function buildRelationsFromAnnotation(ann: AnnotationNode): Relation[] {
  const relations: Relation[] = [];
  if (ann.itemRef.id) {
    relations.push({ sourceId: ann.id, targetId: toNodeId(ann.itemRef.id), type: "item_ref" });
  }
  if (ann.viewRef.id) {
    relations.push({ sourceId: ann.id, targetId: toNodeId(ann.viewRef.id), type: "view_ref" });
  }
  if (ann.entityRef.id) {
    relations.push({
      sourceId: ann.id,
      targetId: toNodeId(ann.entityRef.id),
      type: "entity_ref",
    });
  }
  if (ann.sourceRef.id) {
    relations.push({
      sourceId: ann.id,
      targetId: toNodeId(ann.sourceRef.id),
      type: "source_ref",
    });
  }
  return relations;
}

function buildRelationsFromEntity(entity: EntityNode): Relation[] {
  const relations: Relation[] = [];
  if (entity.itemRef.id) {
    relations.push({
      sourceId: entity.id,
      targetId: toNodeId(entity.itemRef.id),
      type: "item_ref",
    });
  }
  if (entity.parentRef?.id) {
    relations.push({
      sourceId: entity.id,
      targetId: toNodeId(entity.parentRef.id),
      type: "parent_ref",
    });
  }
  return relations;
}

function inferCoordinateFrame(viewNode: DocumentNode): CoordinateFrame | null {
  const baseSchema = viewNode.tableInfo.base_schema;
  const data = viewNode.data;

  if (baseSchema === "Image" || baseSchema === "SequenceFrame") {
    return {
      id: `frame-${viewNode.id}`,
      type: "image2d",
      viewId: viewNode.id,
      dimensions: {
        width: (data["width"] as number) || 0,
        height: (data["height"] as number) || 0,
      },
    };
  }
  if (baseSchema === "Text") {
    return {
      id: `frame-${viewNode.id}`,
      type: "textSpan",
      viewId: viewNode.id,
      dimensions: { length: ((data["content"] as string) || "").length },
    };
  }
  return null;
}

function buildTimelines(
  viewNodes: DocumentNode[],
  annotationNodes: AnnotationNode[],
): Map<string, Timeline> {
  const timelines = new Map<string, Timeline>();

  // Group SequenceFrame views by table name
  const sequenceGroups = new Map<string, DocumentNode[]>();
  for (const view of viewNodes) {
    if (view.tableInfo.base_schema === "SequenceFrame") {
      const group = view.tableInfo.name;
      if (!sequenceGroups.has(group)) sequenceGroups.set(group, []);
      sequenceGroups.get(group)!.push(view);
    }
  }

  for (const [viewName, frames] of sequenceGroups) {
    const frameCount = frames.length;

    // Build tracklet ranges from annotations referencing this view
    const trackletRanges = new Map<NodeId, TimelineRange>();
    const entityFrames = new Map<NodeId, number[]>();

    for (const ann of annotationNodes) {
      if (ann.viewRef.name === viewName && ann.entityRef.id) {
        const entityId = toNodeId(ann.entityRef.id);
        const frameIndex = ann.data["frame_index"] as number | undefined;
        if (frameIndex !== undefined) {
          if (!entityFrames.has(entityId)) entityFrames.set(entityId, []);
          entityFrames.get(entityId)!.push(frameIndex);
        }
      }
    }

    for (const [entityId, frameIndices] of entityFrames) {
      if (frameIndices.length > 0) {
        trackletRanges.set(entityId, {
          start: Math.min(...frameIndices),
          end: Math.max(...frameIndices),
        });
      }
    }

    timelines.set(viewName, {
      viewName,
      frameCount,
      trackletRanges,
    });
  }

  return timelines;
}

// --------------- Factory ---------------

/**
 * Creates a Document from the existing DatasetItem format.
 *
 * This is the bridge between the legacy format and the new document model.
 * The factory reads the DatasetItem shape and builds:
 * - A node map with all items, entities, annotations, and views
 * - Relation edges from reference fields
 * - Coordinate frames inferred from view types
 * - Timelines from SequenceFrame views
 */
export function createDocumentFromDatasetItem(
  datasetItem: DatasetItemShape,
  version: number = 0,
): DocumentImpl {
  const nodes = new Map<NodeId, DocumentNode>();
  const relations: Relation[] = [];
  const coordinateFrames = new Map<NodeId, CoordinateFrame>();
  const viewNodes: DocumentNode[] = [];
  const allAnnotationNodes: AnnotationNode[] = [];

  // 1. Item node
  const itemNode = makeItemNode(datasetItem.item);
  nodes.set(itemNode.id, itemNode);

  // 2. View nodes
  for (const [, viewData] of Object.entries(datasetItem.views)) {
    const viewArray = Array.isArray(viewData) ? viewData : [viewData];
    for (const raw of viewArray) {
      const viewNode = makeViewNode(raw);
      nodes.set(viewNode.id, viewNode);
      viewNodes.push(viewNode);

      // Infer coordinate frame
      const frame = inferCoordinateFrame(viewNode);
      if (frame) coordinateFrames.set(viewNode.id, frame);

      // View → item relation
      const itemRef = extractRef(raw.data, "item_ref");
      if (itemRef.id) {
        relations.push({
          sourceId: viewNode.id,
          targetId: toNodeId(itemRef.id),
          type: "item_ref",
        });
      }
    }
  }

  // 3. Entity nodes
  for (const [, entityData] of Object.entries(datasetItem.entities)) {
    const entityArray = Array.isArray(entityData) ? entityData : [entityData];
    for (const raw of entityArray) {
      const entityNode = makeEntityNode(raw);
      nodes.set(entityNode.id, entityNode);
      relations.push(...buildRelationsFromEntity(entityNode));
    }
  }

  // 4. Annotation nodes
  for (const [, annArray] of Object.entries(datasetItem.annotations)) {
    for (const raw of annArray) {
      const annNode = makeAnnotationNode(raw);
      nodes.set(annNode.id, annNode);
      allAnnotationNodes.push(annNode);
      relations.push(...buildRelationsFromAnnotation(annNode));
    }
  }

  // 5. Build timelines from SequenceFrame views
  const timelines = buildTimelines(viewNodes, allAnnotationNodes);

  return new DocumentImpl({
    id: datasetItem.item.id,
    item: itemNode,
    nodes,
    relations,
    coordinateFrames,
    timelines,
    version,
  });
}
