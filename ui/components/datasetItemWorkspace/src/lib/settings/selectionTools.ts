/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SelectionTool } from "@pixano/core";

export const panTool: SelectionTool = {
  name: "Move image",
  type: "PAN",
  cursor: "move",
};

export const rectangleTool: SelectionTool = {
  name: "Create a bounding box",
  type: "RECTANGLE",
  cursor: "crosshair",
  isSmart: false,
};

export const polygonTool: SelectionTool = {
  name: "Create a polygon",
  type: "POLYGON",
  cursor: "crosshair",
  isSmart: false,
};

export const keyPointTool: SelectionTool = {
  name: "Create key points",
  type: "KEY_POINT",
  cursor: "crosshair",
  isSmart: false,
};

export const removeSmartPointTool: SelectionTool = {
  name: "Negative point selection",
  type: "POINT_SELECTION",
  cursor: "crosshair",
  label: 0,
  isSmart: true,
};

export const addSmartPointTool: SelectionTool = {
  name: "Positive point selection",
  type: "POINT_SELECTION",
  cursor: "crosshair",
  label: 1,
  isSmart: true,
};

export const smartRectangleTool: SelectionTool = {
  name: "Rectangle selection",
  type: "RECTANGLE",
  cursor: "crosshair",
  isSmart: true,
};
