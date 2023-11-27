import { tools } from "@pixano/canvas2d";

export type ToolType = "LABELED_POINT" | "RECTANGLE" | "DELETE" | "PAN" | "CLASSIFICATION";
export type SelectionTool = Partial<Omit<tools.Tool, "onSelect" | "icon">>;

export const panTool: SelectionTool = {
  name: "Move image",
  type: tools.ToolType.Pan,
  cursor: "move",
};

export const smartRectangleTool: SelectionTool = {
  name: "Smart rectangle selection",
  type: tools.ToolType.Rectangle,
  cursor: "crosshair",
};

export const rectangleTool: SelectionTool = {
  name: "Rectangle selection",
  type: tools.ToolType.Rectangle,
  cursor: "crosshair",
};

export const smartMaskTool: SelectionTool = {
  name: " point selection",
  type: tools.ToolType.LabeledPoint,
  cursor: "crosshair",
};
