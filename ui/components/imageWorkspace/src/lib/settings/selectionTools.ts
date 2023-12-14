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

export const smartMaskTool: SelectionTool = {
  name: "point selection",
  type: "LABELED_POINT",
  cursor: "crosshair",
  label: 1,
};
