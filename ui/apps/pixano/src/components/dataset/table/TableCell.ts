/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { renderComponent } from "./render-component";
import BooleanCell from "./TableCells/BooleanCell.svelte";
import DateTimeCell from "./TableCells/DateTimeCell.svelte";
import HistogramCell from "./TableCells/HistogramCell.svelte";
import ImageCell from "./TableCells/ImageCell.svelte";
import NumberCell from "./TableCells/NumberCell.svelte";
import TextCell from "./TableCells/TextCell.svelte";
import VideoCell from "./TableCells/VideoCell.svelte";
import type { DatasetStat } from "$lib/types/dataset";

type CellValue = string | number | boolean | DatasetStat;

// Generic function to create a renderComponent call for a given cell component
const createCellRenderer = (Cell: any) => (value: CellValue) => {
  return renderComponent(Cell, { value: value as never });
};

export const TableCell: Record<string, (value: CellValue) => ReturnType<typeof renderComponent>> = {
  image: createCellRenderer(ImageCell),
  int: createCellRenderer(NumberCell),
  float: createCellRenderer(NumberCell),
  bool: createCellRenderer(BooleanCell),
  str: createCellRenderer(TextCell),
  datetime: createCellRenderer(DateTimeCell),
  video: createCellRenderer(VideoCell),
  histogram: createCellRenderer(HistogramCell),
};
