/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { scaleOrdinal } from "d3";

// Exports
export function ordinalColorScale(range: Iterable<string>) {
  const palette = [
    "#ffc0cb",
    "#7fffd4",
    "#7b68ee",
    "#ff1493",
    "#b0e0e6",
    "#eee8aa",
    "#fa8072",
    "#1e90ff",
    "#ff00ff",
    "#da70d6",
    "#adff2f",
    "#0000ff",
    "#00bfff",
    "#dc143c",
    "#00fa9a",
    "#9400d3",
    "#00ff00",
    "#ffff00",
    "#ffa500",
    "#ff0000",
    "#b03060",
    "#800080",
    "#32cd32",
    "#20b2aa",
    "#d2691e",
    "#000080",
    "#3cb371",
    "#008000",
    "#483d8b",
    "#808000",
    "#7f0000",
    "#2f4f4f",
  ];
  return scaleOrdinal(palette).domain(range);
}

export function isValidURL(urlString: string) {
  try {
    return Boolean(new URL(urlString));
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  } catch (e) {
    return false;
  }
}

export function splitWithLimit(strings: string[], separator: string, limit: number): string[] {
  const result: string[] = [];
  let currentChunk: string[] = [];
  let currentLength = 0;

  for (const str of strings) {
    const strWithSeparator = currentChunk.length ? separator + str : str;
    const newLength = currentLength + strWithSeparator.length;

    if (newLength > limit) {
      // Add the current chunk to the result and start a new chunk
      result.push(currentChunk.join(separator));
      currentChunk = [str];
      currentLength = str.length;
    } else {
      // Add the string to the current chunk
      currentChunk.push(str);
      currentLength = newLength;
    }
  }
  // Add any remaining strings in the last chunk
  if (currentChunk.length) {
    result.push(currentChunk.join(separator));
  }
  return result;
}
