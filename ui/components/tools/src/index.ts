/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Types
export type {
  ToolState,
  ToolEvent,
  ToolSideEffect,
  ToolFSM,
  ToolContext,
  ToolRegistry,
  ToolTransition,
  Point2D,
  PreviewShape,
  LabeledClick,
  AIResult,
  AIRequestParams,
  KeyModifiers,
} from "./types";
export type {
  AllTool,
  BrushSelectionTool,
  LabeledPointTool,
  PolygonOutputMode,
  PolygonSelectionTool,
  SelectionTool,
  ToolPostProcessor,
} from "./selectionTypes";
export { ToolType } from "./selectionTypes";
export {
  addSmartPointTool,
  brushDrawTool,
  brushEraseTool,
  fusionTool,
  keyPointTool,
  panTool,
  polygonTool,
  rectangleTool,
  removeSmartPointTool,
  smartRectangleTool,
} from "./presets";

// Tool FSMs
export { PanToolFSM } from "./fsm/PanToolFSM";
export { RectangleToolFSM } from "./fsm/RectangleToolFSM";
export { PolygonToolFSM } from "./fsm/PolygonToolFSM";
export { PointSelectionToolFSM } from "./fsm/PointSelectionToolFSM";
export { KeypointToolFSM } from "./fsm/KeypointToolFSM";
export { BrushToolFSM } from "./fsm/BrushToolFSM";
export { DeleteToolFSM } from "./fsm/DeleteToolFSM";
export { ClassificationToolFSM } from "./fsm/ClassificationToolFSM";
export { FusionToolFSM } from "./fsm/FusionToolFSM";

// Registry
export { ToolRegistryImpl } from "./impl/ToolRegistryImpl";
