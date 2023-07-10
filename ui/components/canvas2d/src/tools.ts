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

// Exports
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
          return "M200-450v-60h560v60H200Z";
        case 1:
          return "M450-200v-250H200v-60h250v-250h60v250h250v60H510v250h-60Z";
        default:
          return "M468-240q-96-5-162-74t-66-166q0-100 70-170t170-70q97 0 166 66t74 163l-63-20q-11-64-60-106.5T480-660q-75 0-127.5 52.5T300-480q0 67 42.5 116.5T449-303l19 63Zm48 158q-9 1-18 1.5t-18 .5q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 9-.5 18t-1.5 18l-58-18v-18q0-142-99-241t-241-99q-142 0-241 99t-99 241q0 142 99 241t241 99h18l18 58Zm305 22L650-231 600-80 480-480l400 120-151 50 171 171-79 79Z";
      }
    case ToolType.Rectangle:
      return "M180-120q-24 0-42-18t-18-42h60v60Zm-60-148v-83h60v83h-60Zm0-171v-83h60v83h-60Zm0-170v-83h60v83h-60Zm0-171q0-24 18-42t42-18v60h-60Zm148 660v-60h83v60h-83Zm0-660v-60h83v60h-83Zm171 660v-60h83v60h-83Zm0-660v-60h83v60h-83Zm170 660v-60h83v60h-83Zm0-660v-60h83v60h-83Zm171 660v-60h60q0 24-18 42t-42 18Zm0-148v-83h60v83h-60Zm0-171v-83h60v83h-60Zm0-170v-83h60v83h-60Zm0-171v-60q24 0 42 18t18 42h-60Z";
    case ToolType.Pan:
      return "M480-80 317-243l44-44 89 89v-252H198l84 84-44 44L80-480l159-159 44 44-85 85h252v-252l-84 84-44-44 158-158 158 158-44 44-84-84v252h252l-84-84 44-44 158 158-158 158-44-44 84-84H510v252l89-89 44 44L480-80Z";
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
    name: "Point selection" + (label ? " (Positive)" : " (Negative)"),
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
