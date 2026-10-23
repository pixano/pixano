/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ENTITY_COLOR_MODE } from "./colorByCatalogue";
import {
  isHexColor,
  MAX_LEARNED_VALUES,
  MAX_VALUE_KEY_LENGTH,
  normalizeHexColor,
  type NumericRange,
} from "./colorByPalette";

/**
 * Per-dataset "Color by" settings, kept in this browser's local storage.
 *
 * Every record built here uses `Object.fromEntries`, spreads or computed keys, and every lookup
 * `Object.hasOwn`, so a value named `__proto__` or `constructor` is an ordinary key.
 */

/** What is remembered for one attribute. Parts that do not apply to its scale are ignored. */
export interface AttributePalette {
  /** Categories in the order they receive their colors. */
  readonly order?: readonly string[];
  /** Colors the user chose, by category. */
  readonly colors?: Readonly<Record<string, string>>;
  /** Ramp end colors the user chose. */
  readonly ramp?: Readonly<{ low?: string; high?: string }>;
  /** The range of the values seen so far; it only widens. */
  readonly seen?: NumericRange;
}

export interface ColorBySettings {
  /** ENTITY_COLOR_MODE or an attribute id. */
  readonly selected: string;
  readonly palettes: Readonly<Record<string, AttributePalette>>;
}

export const DEFAULT_COLOR_BY_SETTINGS: ColorBySettings = Object.freeze({
  selected: ENTITY_COLOR_MODE,
  palettes: Object.freeze({}),
});

export const COLOR_BY_SETTINGS_VERSION = 1;
export const MAX_PALETTES = 32;
/** Custom colors remembered per attribute. */
export const MAX_CUSTOM_COLORS = 64;
const MAX_SELECTED_LENGTH = 512;

export type KeyValueStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function colorByStorageKey(datasetId: string): string {
  return `pixano.workspace.colorBy.${datasetId}`;
}

/** This browser's local storage, or null where there is none (server rendering, tests, privacy settings). */
export function browserStorage(): KeyValueStorage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function decodeOrder(value: unknown): readonly string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const seen = new Set<string>();
  for (const key of value) {
    if (typeof key !== "string" || key.length > MAX_VALUE_KEY_LENGTH || seen.has(key)) continue;
    seen.add(key);
    if (seen.size >= MAX_LEARNED_VALUES) break;
  }
  return seen.size > 0 ? [...seen] : undefined;
}

function decodeColors(value: unknown): Readonly<Record<string, string>> | undefined {
  if (!isRecord(value)) return undefined;
  const entries: Array<[string, string]> = [];
  for (const [key, color] of Object.entries(value)) {
    if (entries.length >= MAX_CUSTOM_COLORS) break;
    if (key.length > MAX_VALUE_KEY_LENGTH || !isHexColor(color)) continue;
    entries.push([key, color.toLowerCase()]);
  }
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}

function decodeRamp(value: unknown): AttributePalette["ramp"] {
  if (!isRecord(value)) return undefined;
  const low = isHexColor(value.low) ? value.low.toLowerCase() : undefined;
  const high = isHexColor(value.high) ? value.high.toLowerCase() : undefined;
  if (!low && !high) return undefined;
  return { ...(low ? { low } : {}), ...(high ? { high } : {}) };
}

function decodeRange(value: unknown): NumericRange | undefined {
  if (!isRecord(value)) return undefined;
  const { min, max } = value;
  if (typeof min !== "number" || typeof max !== "number") return undefined;
  if (!Number.isFinite(min) || !Number.isFinite(max) || min > max) return undefined;
  return { min, max };
}

function compactPalette(palette: AttributePalette): AttributePalette | undefined {
  const parts: Array<[keyof AttributePalette, unknown]> = [];
  if (palette.order && palette.order.length > 0) parts.push(["order", palette.order]);
  if (palette.colors && Object.keys(palette.colors).length > 0)
    parts.push(["colors", palette.colors]);
  if (palette.ramp && (palette.ramp.low || palette.ramp.high)) parts.push(["ramp", palette.ramp]);
  if (palette.seen) parts.push(["seen", palette.seen]);
  return parts.length > 0 ? Object.fromEntries(parts) : undefined;
}

function decodePalette(value: unknown): AttributePalette | undefined {
  if (!isRecord(value)) return undefined;
  return compactPalette({
    order: decodeOrder(value.order),
    colors: decodeColors(value.colors),
    ramp: decodeRamp(value.ramp),
    seen: decodeRange(value.seen),
  });
}

/** Read stored settings; anything malformed falls back to the defaults, entry by entry. */
export function decodeColorBySettings(raw: string | null | undefined): ColorBySettings {
  if (typeof raw !== "string") return DEFAULT_COLOR_BY_SETTINGS;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return DEFAULT_COLOR_BY_SETTINGS;
  }
  if (!isRecord(parsed) || parsed.v !== COLOR_BY_SETTINGS_VERSION) return DEFAULT_COLOR_BY_SETTINGS;

  const selected =
    typeof parsed.selected === "string" &&
    parsed.selected !== "" &&
    parsed.selected.length <= MAX_SELECTED_LENGTH
      ? parsed.selected
      : ENTITY_COLOR_MODE;
  const entries: Array<[string, AttributePalette]> = [];
  if (isRecord(parsed.palettes)) {
    for (const [attributeId, value] of Object.entries(parsed.palettes)) {
      if (entries.length >= MAX_PALETTES) break;
      const palette = decodePalette(value);
      if (palette) entries.push([attributeId, palette]);
    }
  }
  return { selected, palettes: Object.fromEntries(entries) };
}

export function encodeColorBySettings(settings: ColorBySettings): string {
  return JSON.stringify({
    v: COLOR_BY_SETTINGS_VERSION,
    selected: settings.selected,
    palettes: settings.palettes,
  });
}

export function isDefaultColorBySettings(settings: ColorBySettings): boolean {
  return settings.selected === ENTITY_COLOR_MODE && Object.keys(settings.palettes).length === 0;
}

export function paletteOf(
  settings: ColorBySettings,
  attributeId: string,
): AttributePalette | undefined {
  return Object.hasOwn(settings.palettes, attributeId) ? settings.palettes[attributeId] : undefined;
}

// ─── Updaters: each returns `settings` itself when nothing changes ──────────────

function withPalette(
  settings: ColorBySettings,
  attributeId: string,
  palette: AttributePalette | undefined,
): ColorBySettings {
  const entries = Object.entries(settings.palettes).filter(([id]) => id !== attributeId);
  const compacted = palette ? compactPalette(palette) : undefined;
  if (compacted) entries.push([attributeId, compacted]);
  // Forget the palettes used longest ago, never the selected attribute's.
  while (entries.length > MAX_PALETTES) {
    const oldest = entries.findIndex(([id]) => id !== attributeId && id !== settings.selected);
    if (oldest < 0) break;
    entries.splice(oldest, 1);
  }
  return { selected: settings.selected, palettes: Object.fromEntries(entries) };
}

export function withSelected(settings: ColorBySettings, selected: string): ColorBySettings {
  if (selected === settings.selected || selected === "" || selected.length > MAX_SELECTED_LENGTH) {
    return settings;
  }
  return { selected, palettes: settings.palettes };
}

export function withValueColor(
  settings: ColorBySettings,
  attributeId: string,
  key: string,
  color: string,
): ColorBySettings {
  const hex = normalizeHexColor(color);
  if (!hex || key.length > MAX_VALUE_KEY_LENGTH) return settings;
  const palette = paletteOf(settings, attributeId) ?? {};
  const colors = palette.colors ?? {};
  if (Object.hasOwn(colors, key) && colors[key] === hex) return settings;
  if (!Object.hasOwn(colors, key) && Object.keys(colors).length >= MAX_CUSTOM_COLORS) {
    return settings;
  }
  return withPalette(settings, attributeId, { ...palette, colors: { ...colors, [key]: hex } });
}

export function withRampColor(
  settings: ColorBySettings,
  attributeId: string,
  end: "low" | "high",
  color: string,
): ColorBySettings {
  const hex = normalizeHexColor(color);
  if (!hex) return settings;
  const palette = paletteOf(settings, attributeId) ?? {};
  if (palette.ramp?.[end] === hex) return settings;
  return withPalette(settings, attributeId, { ...palette, ramp: { ...palette.ramp, [end]: hex } });
}

/** Remember a longer category order or a wider range; anything else is ignored. */
export function withLearned(
  settings: ColorBySettings,
  attributeId: string,
  learned: { order?: readonly string[]; seen?: NumericRange },
): ColorBySettings {
  const palette = paletteOf(settings, attributeId) ?? {};
  const order =
    learned.order && learned.order.length > (palette.order?.length ?? 0)
      ? decodeOrder(learned.order)
      : undefined;
  const seen = learned.seen ? decodeRange(learned.seen) : undefined;
  const widens =
    !!seen && (!palette.seen || seen.min < palette.seen.min || seen.max > palette.seen.max);
  if (!order && !widens) return settings;
  return withPalette(settings, attributeId, {
    ...palette,
    ...(order ? { order } : {}),
    ...(widens ? { seen } : {}),
  });
}

/** Back to the automatic colors; the order of the categories and the range are kept. */
export function withoutCustomColors(
  settings: ColorBySettings,
  attributeId: string,
): ColorBySettings {
  const palette = paletteOf(settings, attributeId);
  if (!palette || (!palette.colors && !palette.ramp)) return settings;
  return withPalette(settings, attributeId, { order: palette.order, seen: palette.seen });
}

/** Forget the range seen so far, so it is learned again from the next values. */
export function withoutSeenRange(settings: ColorBySettings, attributeId: string): ColorBySettings {
  const palette = paletteOf(settings, attributeId);
  if (!palette?.seen) return settings;
  return withPalette(settings, attributeId, { ...palette, seen: undefined });
}

/** The same settings without what was learned automatically: what to store when space runs out. */
export function withoutLearned(settings: ColorBySettings): ColorBySettings {
  const entries: Array<[string, AttributePalette]> = [];
  for (const [attributeId, palette] of Object.entries(settings.palettes)) {
    const kept = compactPalette({ colors: palette.colors, ramp: palette.ramp });
    if (kept) entries.push([attributeId, kept]);
  }
  return { selected: settings.selected, palettes: Object.fromEntries(entries) };
}

export function hasCustomColors(palette: AttributePalette | undefined): boolean {
  return !!palette && (!!palette.colors || !!palette.ramp);
}

// ─── Storage ────────────────────────────────────────────────────────────────────

/** The stored settings of a dataset; null when storage is unavailable, fails, or holds nothing. */
export function readStoredColorBySettings(
  storage: KeyValueStorage | null,
  datasetId: string,
): ColorBySettings | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(colorByStorageKey(datasetId));
    return raw === null ? null : decodeColorBySettings(raw);
  } catch {
    return null;
  }
}

/** What a write kept: everything, the settings without what was learned, or nothing. */
export type StoredWrite = "full" | "reduced" | "failed";

/**
 * Store a dataset's settings, or remove them when they are the defaults. When the storage is
 * full, try again without what was learned automatically.
 */
export function writeStoredColorBySettings(
  storage: KeyValueStorage | null,
  datasetId: string,
  settings: ColorBySettings,
): StoredWrite {
  if (!storage) return "failed";
  const key = colorByStorageKey(datasetId);
  try {
    if (isDefaultColorBySettings(settings)) storage.removeItem(key);
    else storage.setItem(key, encodeColorBySettings(settings));
    return "full";
  } catch {
    try {
      storage.setItem(key, encodeColorBySettings(withoutLearned(settings)));
      return "reduced";
    } catch {
      return "failed";
    }
  }
}
