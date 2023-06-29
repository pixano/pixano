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

// Assets
import svg_minus from "../../../apps/annotator/src/assets/icons/minus.svg";
import svg_plus from "../../../apps/annotator/src/assets/icons/plus.svg";
import svg_point from "../../../apps/annotator/src/assets/icons/point.svg";
import svg_box from "../../../apps/annotator/src/assets/icons/box.svg";
import svg_pan from "../../../apps/annotator/src/assets/icons/pan.svg";

export enum ToolType {
  LabeledPoint = "LABELED_POINT",
  Rectangle = "RECTANGLE",
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

interface PanTool extends Tool {
  type: ToolType.Pan;
}

function getIcon(type: ToolType, label?: number): string {
  switch (type) {
    case ToolType.LabeledPoint:
      switch (label) {
        case 0:
          return svg_minus;
        case 1:
          return svg_plus;
        default:
          return svg_point;
      }
    case ToolType.Rectangle:
      return svg_box;
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
    name: "Point selection" + (label ? " (Add)" : " (Remove)"),
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

export function createPanTool(): PanTool {
  return {
    name: "Pan",
    type: ToolType.Pan,
    icon: getIcon(ToolType.Pan),
    cursor: "move",
  } as PanTool;
}

export type { Tool, LabeledPointTool, RectangleTool, PanTool };
