/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { InteractiveImageSegmenter } from "./modelsTypes";

export type ToolType =
  | "POINT_SELECTION"
  | "RECTANGLE"
  | "DELETE"
  | "PAN"
  | "CLASSIFICATION"
  | "KEY_POINT"
  | "POLYGON";

// Exports
type BaseTool<T extends ToolType> = {
  name: string;
  cursor: string;
  postProcessor?: InteractiveImageSegmenter;
  isSmart?: boolean;
  type: T;
};

export type AllTool = BaseTool<
  "RECTANGLE" | "PAN" | "DELETE" | "CLASSIFICATION" | "POLYGON" | "KEY_POINT"
>;

export type LabeledPointTool = BaseTool<"POINT_SELECTION"> & {
  label: number;
};

export type SelectionTool = AllTool | LabeledPointTool;
