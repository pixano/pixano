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
