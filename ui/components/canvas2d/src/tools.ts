/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { icons } from "@pixano/core";

import type { InteractiveImageSegmenter } from "@pixano/models";

// Exports
export enum ToolType {
  PointSelection = "POINT_SELECTION",
  Rectangle = "RECTANGLE",
  Delete = "DELETE",
  Pan = "PAN",
  Classification = "CLASSIFICATION",
}

interface Tool {
  name: string;
  type: ToolType;
  icon: string;
  cursor: string;
  onSelect?: () => void;
  isSmart?: boolean;
  modes?: Record<string, Tool>;
  postProcessor?: InteractiveImageSegmenter;
}

interface PointSelectionTool extends Tool {
  modes: Record<string, Tool>;
  type: ToolType.PointSelection;
}

interface PointSelectionModeTool extends Tool {
  label: number;
  type: ToolType.PointSelection;
}

interface RectangleTool extends Tool {
  type: ToolType.Rectangle;
}

interface DeleteTool extends Tool {
  type: ToolType.Delete;
}

interface PanTool extends Tool {
  type: ToolType.Pan;
}

interface ClassificationTool extends Tool {
  type: ToolType.Classification;
}

export function createPointSelectionTool(): PointSelectionTool {
  return {
    name: "Point selection",
    type: ToolType.PointSelection,
    icon: icons.svg_point,
    cursor: "crosshair",
    modes: { plus: createPointPlusTool(), minus: createPointMinusTool() },
  } as PointSelectionTool;
}

export function createPointPlusTool(): PointSelectionModeTool {
  return {
    name: "Positive point selection",
    label: 1,
    type: ToolType.PointSelection,
    icon: icons.svg_point_plus,
    cursor: "crosshair",
  } as PointSelectionModeTool;
}

export function createPointMinusTool(): PointSelectionModeTool {
  return {
    name: "Negative point selection",
    label: 0,
    type: ToolType.PointSelection,
    icon: icons.svg_point_minus,
    cursor: "crosshair",
  } as PointSelectionModeTool;
}

export function createRectangleTool(): RectangleTool {
  return {
    name: "Rectangle selection",
    type: ToolType.Rectangle,
    icon: icons.svg_rectangle,
    cursor: "crosshair",
  } as RectangleTool;
}

export function createDeleteTool(): DeleteTool {
  return {
    name: "Delete selection",
    type: ToolType.Delete,
    icon: icons.svg_delete,
    cursor: "auto",
  } as DeleteTool;
}

export function createPanTool(): PanTool {
  return {
    name: "Move image",
    type: ToolType.Pan,
    icon: icons.svg_pan,
    cursor: "move",
  } as PanTool;
}

export function createClassifTool(): ClassificationTool {
  return {
    name: "Classification",
    type: ToolType.Classification,
    icon: icons.svg_classify,
    cursor: "default",
  } as ClassificationTool;
}

export type {
  Tool,
  PointSelectionTool,
  PointSelectionModeTool,
  RectangleTool,
  DeleteTool,
  PanTool,
  ClassificationTool,
};
