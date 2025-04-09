/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { scaleOrdinal } from "d3";
import { schemeSet3 } from "d3-scale-chromatic";

// Exports
export function ordinalColorScale(range: Iterable<string>) {
  return scaleOrdinal(schemeSet3).domain(range);
}

export function isLuminanceHigh(backgroundColor: string): boolean {
  //compute background color luminance to choose either white or black font color
  const hex = backgroundColor.replace(/^#/, "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 128;
}
