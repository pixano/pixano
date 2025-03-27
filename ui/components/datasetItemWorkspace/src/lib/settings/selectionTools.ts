/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "@pixano/canvas2d/src/tools";
import type { SelectionTool } from "@pixano/core";

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

export const polygonTool: SelectionTool = {
  name: "Create a polygon",
  type: ToolType.Polygon,
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

export const removeSmartPointTool: SelectionTool = {
  name: "Negative point selection",
  type: ToolType.PointSelection,
  cursor: "crosshair",
  label: 0,
  isSmart: true,
};

export const addSmartPointTool: SelectionTool = {
  name: "Positive point selection",
  type: ToolType.PointSelection,
  cursor: "crosshair",
  label: 1,
  isSmart: true,
};

export const smartRectangleTool: SelectionTool = {
  name: "Rectangle selection",
  type: ToolType.Rectangle,
  cursor: "crosshair",
  isSmart: true,
};
