/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { color as d3Color, interpolateHcl } from "d3";

import type { ColorByAttribute } from "./colorByCatalogue";
import { paletteColorAt } from "$lib/utils/coreUtils";

/**
 * Colors for the values of a categorical attribute, in the order values receive them.
 *
 * All come from the entity palette, without its pink (the color of drafts and unlinked shapes)
 * and without the colors too close to gray or too dark to read on the canvas.
 */
export const ATTRIBUTE_PALETTE: readonly string[] = Object.freeze([
  "#1e90ff",
  "#ffff00",
  "#ff0000",
  "#ff00ff",
  "#32cd32",
  "#808000",
  "#ffa500",
  "#20b2aa",
  "#ff1493",
  "#00ff00",
  "#fa8072",
  "#00bfff",
  "#da70d6",
  "#7fffd4",
  "#7b68ee",
  "#00fa9a",
  "#d2691e",
  "#3cb371",
  "#adff2f",
]);

/** Shapes whose attribute has no value: opaque, unlike the translucent de-emphasis gray. */
export const NO_VALUE_COLOR = "#d4d4d8";

/** Drafts, previews and shapes linked to no known object. */
export const UNLINKED_COLOR = paletteColorAt(0);

export const DEFAULT_RAMP: Readonly<{ low: string; high: string }> = Object.freeze({
  low: "#1e90ff",
  high: "#ffff00",
});

/** Values whose order is remembered per attribute; later values get a hashed color. */
export const MAX_LEARNED_VALUES = 64;
/** Longer values are colored by hash and never remembered. */
export const MAX_VALUE_KEY_LENGTH = 200;

export interface NumericRange {
  readonly min: number;
  readonly max: number;
}

export interface NumericDomain extends NumericRange {
  /** "fixed" when the attribute defines its range, "seen" when learned from the values met so far. */
  readonly source: "fixed" | "seen";
}

/** A category key, a number, or null for "no value". */
export type AttributeValue = string | number | null;

const EMPTY_ORDER: readonly string[] = Object.freeze<string[]>([]);
const HEX_COLOR = /^#[0-9a-f]{6}$/i;

/** Read an attribute's raw value as a category key or a number, or null when it has no value. */
export function readAttributeValue(
  attribute: Pick<ColorByAttribute, "scale" | "fieldType" | "noValueBelow">,
  raw: unknown,
): AttributeValue {
  if (attribute.scale === "numeric") {
    let value: number;
    if (typeof raw === "number") value = raw;
    else if (typeof raw === "string" && raw.trim() !== "") value = Number(raw.trim());
    else return null;
    if (!Number.isFinite(value)) return null;
    if (attribute.noValueBelow !== undefined && value < attribute.noValueBelow) return null;
    return value;
  }
  if (attribute.fieldType === "bool") {
    if (typeof raw === "boolean") return String(raw);
    if (typeof raw === "string") {
      const lowered = raw.trim().toLowerCase();
      if (lowered === "true" || lowered === "false") return lowered;
    }
    return null;
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    return trimmed === "" ? null : trimmed;
  }
  if (typeof raw === "number") return Number.isFinite(raw) ? String(raw) : null;
  if (typeof raw === "boolean" || typeof raw === "bigint") return String(raw);
  return null;
}

const collator = new Intl.Collator("en", { numeric: true });

/** Natural order of category keys ("2" before "10"), stable for keys the collator ties. */
export function compareValueKeys(a: string, b: string): number {
  return collator.compare(a, b) || (a < b ? -1 : a > b ? 1 : 0);
}

/**
 * The `count` first keys in natural order, sorted. Runs in O(n log count), so a record with a
 * huge number of distinct values never sorts them all.
 */
export function firstKeys(keys: Iterable<string>, count: number): string[] {
  const kept: string[] = [];
  if (count <= 0) return kept;
  for (const key of keys) {
    if (kept.length === count && compareValueKeys(key, kept[count - 1]) >= 0) continue;
    let low = 0;
    let high = kept.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (compareValueKeys(kept[middle], key) < 0) low = middle + 1;
      else high = middle;
    }
    kept.splice(low, 0, key);
    if (kept.length > count) kept.pop();
  }
  return kept;
}

/**
 * The order in which values receive their colors, extended with the seeds and the values just
 * seen. Known values keep their place; new ones are appended in natural order, up to
 * MAX_LEARNED_VALUES. Returns `order` itself (or a shared empty array) when nothing is added.
 */
export function extendCategoricalOrder(
  order: readonly string[] | undefined,
  seeds: readonly string[] | undefined,
  observed: Iterable<string>,
): readonly string[] {
  const base = order ?? EMPTY_ORDER;
  const room = MAX_LEARNED_VALUES - base.length;
  if (room <= 0) return base;

  const known = new Set(base);
  const added: string[] = [];
  for (const seed of seeds ?? []) {
    if (!known.has(seed)) {
      known.add(seed);
      added.push(seed);
    }
  }
  const fresh = new Set<string>();
  for (const key of observed) {
    if (!known.has(key) && key.length <= MAX_VALUE_KEY_LENGTH) fresh.add(key);
  }
  for (const key of firstKeys(fresh, room - added.length)) added.push(key);
  if (added.length === 0) return base;
  return base.concat(added.slice(0, room));
}

/** A stable palette slot for a value with no remembered place (FNV-1a). */
export function hashSlot(key: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < key.length; i++) {
    hash ^= key.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) % ATTRIBUTE_PALETTE.length;
}

/** The color of a category: the user's choice, else its slot's palette color. */
export function categoricalColor(
  key: string,
  slotByKey: ReadonlyMap<string, number>,
  overrides?: Readonly<Record<string, string>>,
): string {
  if (overrides && Object.hasOwn(overrides, key)) return overrides[key];
  const slot = slotByKey.get(key) ?? hashSlot(key);
  return ATTRIBUTE_PALETTE[slot % ATTRIBUTE_PALETTE.length];
}

export function isHexColor(value: unknown): value is string {
  return typeof value === "string" && HEX_COLOR.test(value);
}

/** Any CSS color as lowercase `#rrggbb`, or null when it is not a color. */
export function normalizeHexColor(value: unknown): string | null {
  if (typeof value !== "string" || value.trim() === "") return null;
  return d3Color(value.trim())?.formatHex() ?? null;
}

/** Widen a remembered range to include the values just seen; returns `seen` when it holds them. */
export function widenRange(
  seen: NumericRange | undefined,
  observed: NumericRange | null,
): NumericRange | undefined {
  if (!observed) return seen;
  if (!seen) return { min: observed.min, max: observed.max };
  if (observed.min >= seen.min && observed.max <= seen.max) return seen;
  return { min: Math.min(seen.min, observed.min), max: Math.max(seen.max, observed.max) };
}

/** The range a numeric attribute is colored over: its own if it has one, else the values seen. */
export function resolveNumericDomain(
  fixed: readonly [number, number] | undefined,
  seen: NumericRange | undefined,
): NumericDomain | null {
  if (fixed) return { min: fixed[0], max: fixed[1], source: "fixed" };
  if (seen) return { min: seen.min, max: seen.max, source: "seen" };
  return null;
}

/** A value's position on the ramp, clamped to [0, 1]; the middle when the range is one value. */
export function rampPosition(value: number, domain: NumericRange | null): number {
  if (!domain || !(domain.max > domain.min)) return 0.5;
  return Math.min(1, Math.max(0, (value - domain.min) / (domain.max - domain.min)));
}

export interface Ramp {
  readonly low: string;
  readonly high: string;
  /** The color at position t in [0, 1], as `#rrggbb`. */
  colorAt(t: number): string;
  /** n colors evenly spaced from low to high. */
  stops(n: number): string[];
}

const RAMP_STEPS = 256;
const MAX_CACHED_RAMPS = 32;
const rampCache = new Map<string, Ramp>();

/** A color ramp between two colors, interpolated in HCL and tabulated as hex. */
export function createRamp(low: string = DEFAULT_RAMP.low, high: string = DEFAULT_RAMP.high): Ramp {
  const cacheKey = `${low}|${high}`;
  const cached = rampCache.get(cacheKey);
  if (cached) return cached;

  const interpolate = interpolateHcl(low, high);
  const table = Array.from(
    { length: RAMP_STEPS },
    (_, i) => normalizeHexColor(interpolate(i / (RAMP_STEPS - 1))) ?? low,
  );
  table[0] = low;
  table[RAMP_STEPS - 1] = high;

  const colorAt = (t: number): string => {
    const clamped = Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0.5;
    return table[Math.round(clamped * (RAMP_STEPS - 1))];
  };
  const ramp: Ramp = {
    low,
    high,
    colorAt,
    stops: (n) => Array.from({ length: n }, (_, i) => colorAt(n <= 1 ? 0.5 : i / (n - 1))),
  };

  if (rampCache.size >= MAX_CACHED_RAMPS) rampCache.clear();
  rampCache.set(cacheKey, ramp);
  return ramp;
}

/** A number as the legend shows it: integers as they are, others with at most 3 decimals. */
export function formatAttributeNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
}
