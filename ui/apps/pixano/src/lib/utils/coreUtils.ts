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

const ABSOLUTE_URL_RE = /^(?:[a-z][a-z0-9+.-]*:)?\/\//i;
const INLINE_URL_RE = /^(?:blob:|data:)/i;

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

export function isAbsoluteOrInlineUrl(url: string): boolean {
  return ABSOLUTE_URL_RE.test(url) || INLINE_URL_RE.test(url);
}

export function toClientAssetUrl(url: string): string {
  if (isAbsoluteOrInlineUrl(url)) {
    return url;
  }
  return `/${url.replace(/^\/+/, "")}`;
}

export function normalizeMediaUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return trimmed;

  if (isAbsoluteOrInlineUrl(trimmed)) {
    return trimmed;
  }

  const normalized = trimmed.replace(/^\/+/, "");
  if (
    normalized.startsWith("datasets/") ||
    normalized.startsWith("views/") ||
    normalized.startsWith("media/")
  ) {
    return normalized;
  }

  return `media/${normalized}`;
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

export const nowTimestamp = (): string => new Date().toISOString().replace(/Z$/, "+00:00");

export const removeFieldFromValue = <T extends object, K extends keyof T>(
  value: T,
  field: K,
): Omit<T, K> => {
  const rest = { ...value } as T & Record<PropertyKey, unknown>;
  delete rest[field as PropertyKey];
  return rest as Omit<T, K>;
};

export function isLuminanceHigh(backgroundColor: string): boolean {
  const hex = backgroundColor.replace(/^#/, "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 128;
}
