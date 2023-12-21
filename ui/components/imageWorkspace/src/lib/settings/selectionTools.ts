import type { SelectionTool } from "@pixano/core";

export const panTool: SelectionTool = {
  name: "Move image",
  type: "PAN",
  cursor: "move",
};

export const smartRectangleTool: SelectionTool = {
  name: "Smart rectangle selection",
  type: "RECTANGLE",
  cursor: "crosshair",
  isSmart: true,
};

export const rectangleTool: SelectionTool = {
  name: "Rectangle selection",
  type: "RECTANGLE",
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
