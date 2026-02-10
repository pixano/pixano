/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { ToolType } from "../../../../canvas2d/src/tools";
import type { InteractiveImageSegmenter } from "./modelsTypes";

// Exports
type BaseTool<T extends ToolType> = {
  name: string;
  cursor: string;
  postProcessor?: InteractiveImageSegmenter;
  isSmart?: boolean;
  type: T;
};

export type AllTool = BaseTool<
  | ToolType.Rectangle
  | ToolType.Pan
  | ToolType.Delete
  | ToolType.Classification
  | ToolType.Polygon
  | ToolType.Keypoint
  | ToolType.Fusion
>;

export type LabeledPointTool = BaseTool<ToolType.PointSelection> & {
  label: number;
};

export type BrushSelectionTool = BaseTool<ToolType.Brush> & {
  mode: "draw" | "erase";
};

export type SelectionTool = AllTool | LabeledPointTool | BrushSelectionTool;
