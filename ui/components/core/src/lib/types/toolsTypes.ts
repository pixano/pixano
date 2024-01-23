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

export type ToolType =
  | "POINT_SELECTION"
  | "RECTANGLE"
  | "DELETE"
  | "PAN"
  | "CLASSIFICATION"
  | "POLYGON";

// Exports
type BaseTool<T extends ToolType> = {
  name: string;
  cursor: string;
  postProcessor?: InteractiveImageSegmenter;
  isSmart?: boolean;
  type: T;
};

export type AllTool = BaseTool<"RECTANGLE" | "PAN" | "DELETE" | "CLASSIFICATION" | "POLYGON">;

export type LabeledPointTool = BaseTool<"POINT_SELECTION"> & {
  label: number;
};

export type SelectionTool = AllTool | LabeledPointTool;
