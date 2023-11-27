import { tools } from "@pixano/canvas2d";

export type SelectionTool = Partial<Omit<tools.Tool, "onSelect" | "icon">>;

export const panTool: SelectionTool = {
  name: "Move image",
  type: tools.ToolType.Pan,
  cursor: "move",
};

export const rectangleTool: SelectionTool = {
  name: "Rectangle selection",
  type: tools.ToolType.Rectangle,
  cursor: "crosshair",
};
