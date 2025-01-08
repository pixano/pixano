/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetStat } from "./lib/types/dataset";

// Exports

export type CellData =
  | TextCellData
  | ImageCellData
  | IntCellData
  | FloatCellData
  | BooleanCellData
  | HistogramCellData;

interface ImageCellData {
  dtype: "image";
  value: string;
}
interface TextCellData {
  dtype: "str";
  value: string;
}
interface IntCellData {
  dtype: "int";
  value: number;
}
interface FloatCellData {
  dtype: "float";
  value: number;
}

interface BooleanCellData {
  dtype: "bool";
  value: boolean;
}
interface HistogramCellData {
  dtype: "histogram";
  value: DatasetStat;
}
