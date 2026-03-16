/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DocumentImpl, type DocumentNode, type NodeId } from "$lib/document";
import { createPixanoContext } from "$lib/stores/createPixanoContext";
import type { ToolBridge } from "$lib/types/store";
import {
  BrushToolFSM,
  PanToolFSM,
  PolygonToolFSM,
  PolylineToolFSM,
  RectangleToolFSM,
  ToolType,
  type SelectionTool,
  type ToolFSM,
} from "$lib/tools";

export function createInternalToolBridge(selectedItemId: string): ToolBridge {
  const now = new Date().toISOString();
  const itemNodeId = `item-${selectedItemId || "unknown"}` as NodeId;
  const itemNode: DocumentNode = {
    id: itemNodeId,
    nodeType: "item",
    tableInfo: {
      name: "item",
      group: "items",
      base_schema: "item",
    },
    data: {},
    createdAt: now,
    updatedAt: now,
  };

  const doc = new DocumentImpl({
    id: `canvas2d-${selectedItemId || "unknown"}`,
    item: itemNode,
    nodes: new Map([[itemNodeId, itemNode]]),
    relations: [],
    coordinateFrames: new Map(),
    timelines: new Map(),
    version: 0,
  });

  return createPixanoContext({
    document: doc,
    initialTool: new PanToolFSM(),
  }).toolBridge;
}

export function createToolFSMForSelection(tool: SelectionTool): ToolFSM | null {
  switch (tool.type) {
    case ToolType.Pan:
      return new PanToolFSM();
    case ToolType.Rectangle:
      return new RectangleToolFSM({ isSmart: !!tool.isSmart });
    case ToolType.Polygon:
      return new PolygonToolFSM({ defaultOutputMode: tool.outputMode });
    case ToolType.Polyline:
      return new PolylineToolFSM();
    case ToolType.Brush:
      return new BrushToolFSM(tool.mode);
    default:
      return null;
  }
}
