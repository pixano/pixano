/**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
*/

// Imports
import {
  svg_point,
  svg_point_plus,
  svg_point_minus,
  svg_rectangle,
  svg_delete,
  svg_pan,
} from "@pixano/core/src/icons";

// Exports
export enum ToolType {
  LabeledPoint = "LABELED_POINT",
  Rectangle = "RECTANGLE",
  Delete = "DELETE",
  Pan = "PAN",
}

interface Tool {
  name: string;
  type: ToolType;
  icon: string;
  cursor: string;
  onSelect: () => void;
  postProcessor: any;
}

interface MultiModalTool extends Tool {
  modes: Array<Tool>;
}
interface LabeledPointTool extends Tool {
  type: ToolType.LabeledPoint;
  label: number;
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

function getIcon(type: ToolType, label?: number): string {
  switch (type) {
    case ToolType.LabeledPoint:
      switch (label) {
        case 0:
          return svg_point_minus;
        case 1:
          return svg_point_plus;
        default:
          return svg_point;
      }
    case ToolType.Rectangle:
      return svg_rectangle;
    case ToolType.Delete:
      return svg_delete;
    case ToolType.Pan:
      return svg_pan;
  }
}

export function createMultiModalTool(
  name: string,
  type: ToolType,
  tools: Array<Tool>
): MultiModalTool {
  return {
    name: name,
    type: type,
    icon: getIcon(type),
    modes: tools,
  } as MultiModalTool;
}

export function createLabeledPointTool(label: number): LabeledPointTool {
  return {
    name: (label ? "Positive" : "Negative") + " point selection",
    type: ToolType.LabeledPoint,
    label: label,
    icon: getIcon(ToolType.LabeledPoint, label),
    cursor: "crosshair",
  } as LabeledPointTool;
}

export function createRectangleTool(): RectangleTool {
  return {
    name: "Rectangle selection",
    type: ToolType.Rectangle,
    icon: getIcon(ToolType.Rectangle),
    cursor: "crosshair",
  } as RectangleTool;
}

export function createDeleteTool(): DeleteTool {
  return {
    name: "Delete selection",
    type: ToolType.Delete,
    icon: getIcon(ToolType.Delete),
    cursor: "auto",
  } as DeleteTool;
}

export function createPanTool(): PanTool {
  return {
    name: "Move image",
    type: ToolType.Pan,
    icon: getIcon(ToolType.Pan),
    cursor: "move",
  } as PanTool;
}

export type { Tool, LabeledPointTool, RectangleTool, DeleteTool, PanTool };
