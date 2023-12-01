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
import type { InteractiveImageSegmenter } from "./modelsTypes";

// Exports
export enum ToolType {
  LabeledPoint = "LABELED_POINT",
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
  onSelect: () => void;
  postProcessor: InteractiveImageSegmenter;
  isSmart?: boolean;
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

interface ClassificationTool extends Tool {
  type: ToolType.Classification;
}

export type {
  Tool,
  LabeledPointTool,
  RectangleTool,
  DeleteTool,
  PanTool,
  ClassificationTool,
  MultiModalTool,
};
