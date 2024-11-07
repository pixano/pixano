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

export function isValidURL(urlString: string) {
  try {
    return Boolean(new URL(urlString));
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
