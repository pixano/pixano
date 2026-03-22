/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  ToolType,
  type BrushSelectionTool,
  type InteractiveSegmenterSelectionTool,
  type PolygonSelectionTool,
  type PolylineSelectionTool,
  type SelectionTool,
  type VOSSelectionTool,
} from "$lib/types/tools";

export const panTool: SelectionTool = {
  name: "Selection & Move image",
  type: ToolType.Pan,
  cursor: "move",
};

export const rectangleTool: SelectionTool = {
  name: "Create a bounding box",
  type: ToolType.Rectangle,
  cursor: "crosshair",
  isSmart: false,
};

export const interactiveSegmenterTool: InteractiveSegmenterSelectionTool = {
  name: "Interactive smart segmentation",
  type: ToolType.InteractiveSegmenter,
  cursor: "crosshair",
  promptMode: "positive",
};

export const vosTool: VOSSelectionTool = {
  name: "Video Object Segmentation (Smart Track)",
  type: ToolType.VOS,
  cursor: "crosshair",
  promptMode: "positive",
};

export const polygonTool: PolygonSelectionTool = {
  name: "Create a polygon",
  type: ToolType.Polygon,
  cursor: "crosshair",
  isSmart: false,
  outputMode: "polygon",
};

export const polylineTool: PolylineSelectionTool = {
  name: "Create a polyline",
  type: ToolType.Polyline,
  cursor: "crosshair",
  isSmart: false,
};

export const keyPointTool: SelectionTool = {
  name: "Create keypoints",
  type: ToolType.Keypoint,
  cursor: "crosshair",
  isSmart: false,
};

export const fusionTool: SelectionTool = {
  name: "Associate objects",
  type: ToolType.Fusion,
  cursor: "default",
  isSmart: false,
};

export const brushDrawTool: BrushSelectionTool = {
  name: "Brush (Draw)",
  type: ToolType.Brush,
  cursor: "none",
  mode: "draw",
};

export const brushEraseTool: BrushSelectionTool = {
  name: "Brush (Erase)",
  type: ToolType.Brush,
  cursor: "none",
  mode: "erase",
};
