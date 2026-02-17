/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Canonical UI tool identifiers.
 *
 * These values are persisted in stores and compared across packages.
 */
export enum ToolType {
  PointSelection = "POINT_SELECTION",
  Rectangle = "RECTANGLE",
  Polygon = "POLYGON",
  Keypoint = "KEY_POINT",
  Delete = "DELETE",
  Pan = "PAN",
  Fusion = "FUSION",
  Classification = "CLASSIFICATION",
  Brush = "BRUSH",
}

export interface ToolPostProcessor {
  reset(): void;
}

type BaseTool<T extends ToolType> = {
  name: string;
  cursor: string;
  type: T;
  isSmart?: boolean;
  postProcessor?: ToolPostProcessor;
};

export type PolygonOutputMode = "polygon" | "mask";

export type AllTool = BaseTool<
  | ToolType.Rectangle
  | ToolType.Pan
  | ToolType.Delete
  | ToolType.Classification
  | ToolType.Keypoint
  | ToolType.Fusion
>;

export type LabeledPointTool = BaseTool<ToolType.PointSelection> & {
  label: number;
};

export type PolygonSelectionTool = BaseTool<ToolType.Polygon> & {
  outputMode: PolygonOutputMode;
};

export type BrushSelectionTool = BaseTool<ToolType.Brush> & {
  mode: "draw" | "erase";
};

export type SelectionTool = AllTool | LabeledPointTool | BrushSelectionTool | PolygonSelectionTool;
