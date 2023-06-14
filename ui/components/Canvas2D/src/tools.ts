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

export enum ToolType {
  LabeledPoint = "LABELED_POINT",
  Rectangle = "RECTANGLE",
  Pan = "PAN",
}

interface Tool {
  type: ToolType;
  icon: string;
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
          return "icons/minus.svg";
        case 1:
          return "icons/plus.svg";
        default:
          return "icons/point.svg";
      }
      case ToolType.Rectangle:
        return "icons/box.svg";
      case ToolType.Pan:
        return "icons/pan.svg";
    }
}

export function createMultiModalTool(type: ToolType, tools: Array<Tool>): MultiModalTool {
  return { type: type, icon: getIcon(type), modes: tools } as MultiModalTool;
}

export function createLabeledPointTool(label: number): LabeledPointTool {
  return {
    type: ToolType.LabeledPoint,
    label: label,
    icon: getIcon(ToolType.LabeledPoint, label),
  } as LabeledPointTool;
}

export function createRectangleTool(): RectangleTool {
  return { type: ToolType.Rectangle, icon: getIcon(ToolType.Rectangle) } as RectangleTool;
}

export function createPanTool(): PanTool {
  return { type: ToolType.Pan, icon: getIcon(ToolType.Pan) } as PanTool;
}

export type { Tool, LabeledPointTool, RectangleTool, PanTool };
