/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const defaultPalette = [
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

export function ordinalColorScale(range: Iterable<string>) {
  const ids = [...range];
  const colorById = new Map<string, string>();
  ids.forEach((id, index) => {
    colorById.set(id, defaultPalette[index % defaultPalette.length]);
  });
  return (id: string) => colorById.get(id) ?? defaultPalette[0];
}

export function isValidURL(urlString: string) {
  try {
    return Boolean(new URL(urlString));
  } catch {
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
      result.push(currentChunk.join(separator));
      currentChunk = [str];
      currentLength = str.length;
    } else {
      currentChunk.push(str);
      currentLength = newLength;
    }
  }

  if (currentChunk.length) {
    result.push(currentChunk.join(separator));
  }

  return result;
}

export const nowTimestamp = (): string =>
  new Date().toISOString().replace(/Z$/, "+00:00");

export function isLuminanceHigh(backgroundColor: string): boolean {
  const hex = backgroundColor.replace(/^#/, "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 128;
}
