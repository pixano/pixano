/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

import type { DatasetStat } from "./lib/types/datasetTypes";

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
