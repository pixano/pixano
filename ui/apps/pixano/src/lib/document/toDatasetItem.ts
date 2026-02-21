/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationNode, Document, DocumentNode, EntityNode } from "$lib/types/document";

// --------------- DatasetItem output shape ---------------
// Minimal structural type matching @pixano/core DatasetItemType

interface DatasetItemBaseData {
  id: string;
  table_info: { name: string; group: string; base_schema: string };
  created_at: string;
  updated_at: string;
  data: Record<string, unknown>;
}

interface DatasetItemShape {
  item: DatasetItemBaseData;
  entities: Record<string, DatasetItemBaseData[]>;
  annotations: Record<string, DatasetItemBaseData[]>;
  views: Record<string, DatasetItemBaseData | DatasetItemBaseData[]>;
}

// --------------- Helpers ---------------

function nodeToBaseData(node: DocumentNode): DatasetItemBaseData {
  return {
    id: node.id,
    table_info: {
      name: node.tableInfo.name,
      group: node.tableInfo.group,
      base_schema: node.tableInfo.base_schema,
    },
    created_at: node.createdAt,
    updated_at: node.updatedAt,
    data: { ...node.data },
  };
}

function annotationToBaseData(node: AnnotationNode): DatasetItemBaseData {
  const base = nodeToBaseData(node);
  // Restore reference fields into data (backend format)
  base.data["item_ref"] = { ...node.itemRef };
  base.data["view_ref"] = { ...node.viewRef };
  base.data["entity_ref"] = { ...node.entityRef };
  base.data["source_ref"] = { ...node.sourceRef };
  return base;
}

function entityToBaseData(node: EntityNode): DatasetItemBaseData {
  const base = nodeToBaseData(node);
  base.data["item_ref"] = { ...node.itemRef };
  if (node.parentRef) {
    base.data["parent_ref"] = { ...node.parentRef };
  }
  return base;
}

// --------------- Converter ---------------

/**
 * Converts a Document back to the DatasetItem format for persistence.
 *
 * This is the inverse of `createDocumentFromDatasetItem()`.
 * Together they form a lossless round-trip:
 *   DatasetItem → Document → DatasetItem (identical)
 */
export function toDatasetItem(document: Document): DatasetItemShape {
  const item = nodeToBaseData(document.item);

  // Group entities by table name
  const entities: Record<string, DatasetItemBaseData[]> = {};
  for (const entity of document.getEntities()) {
    const tableName = entity.tableInfo.name;
    if (!entities[tableName]) entities[tableName] = [];
    entities[tableName].push(entityToBaseData(entity));
  }

  // Group annotations by table name
  const annotations: Record<string, DatasetItemBaseData[]> = {};
  for (const ann of document.getAnnotations()) {
    const tableName = ann.tableInfo.name;
    if (!annotations[tableName]) annotations[tableName] = [];
    annotations[tableName].push(annotationToBaseData(ann));
  }

  // Group views by table name
  // Views can be single (Image) or arrays (SequenceFrame[])
  const viewsByTable = new Map<string, DocumentNode[]>();
  for (const node of document.getNodes()) {
    if (node.nodeType === "view") {
      const tableName = node.tableInfo.name;
      if (!viewsByTable.has(tableName)) viewsByTable.set(tableName, []);
      viewsByTable.get(tableName)!.push(node);
    }
  }

  const views: Record<string, DatasetItemBaseData | DatasetItemBaseData[]> = {};
  for (const [tableName, viewNodes] of viewsByTable) {
    if (viewNodes.length === 1 && viewNodes[0].tableInfo.base_schema !== "SequenceFrame") {
      // Single view (e.g., Image)
      const viewData = nodeToBaseData(viewNodes[0]);
      // Restore view reference fields
      if (viewNodes[0].data["item_ref"]) {
        viewData.data["item_ref"] = viewNodes[0].data["item_ref"];
      }
      if (viewNodes[0].data["parent_ref"]) {
        viewData.data["parent_ref"] = viewNodes[0].data["parent_ref"];
      }
      views[tableName] = viewData;
    } else {
      // Multiple views (e.g., SequenceFrame array)
      views[tableName] = viewNodes.map((vn) => {
        const viewData = nodeToBaseData(vn);
        if (vn.data["item_ref"]) {
          viewData.data["item_ref"] = vn.data["item_ref"];
        }
        if (vn.data["parent_ref"]) {
          viewData.data["parent_ref"] = vn.data["parent_ref"];
        }
        return viewData;
      });
    }
  }

  return { item, entities, annotations, views };
}
