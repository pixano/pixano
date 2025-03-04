/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { createRender } from "svelte-headless-table";

import type { DatasetStat } from "@pixano/core";

import BooleanCell from "./TableCells/BooleanCell.svelte";
import DateTimeCell from "./TableCells/DateTimeCell.svelte";
import HistogramCell from "./TableCells/HistogramCell.svelte";
import ImageCell from "./TableCells/ImageCell.svelte";
import NumberCell from "./TableCells/NumberCell.svelte";
import TextCell from "./TableCells/TextCell.svelte";
import VideoCell from "./TableCells/VideoCell.svelte";

type cellType = string | number | boolean | DatasetStat;

// Generic function to create render function for a given component
const createRenderFunction = (Cell) => (value: { value: cellType }) => {
  return createRender(Cell, {
    value: value.value,
  });
};

export const TableCell = {
  image: createRenderFunction(ImageCell),
  int: createRenderFunction(NumberCell),
  float: createRenderFunction(NumberCell),
  bool: createRenderFunction(BooleanCell),
  str: createRenderFunction(TextCell),
  datetime: createRenderFunction(DateTimeCell),
  video: createRenderFunction(VideoCell),
  histogram: createRenderFunction(HistogramCell),
};
