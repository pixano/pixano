/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  ENTITY_COLOR_MODE,
  type ColorByAttribute,
  type ColorByCatalogue,
} from "./colorByCatalogue";
import {
  categoricalColor,
  compareValueKeys,
  createRamp,
  extendCategoricalOrder,
  NO_VALUE_COLOR,
  rampPosition,
  readAttributeValue,
  resolveNumericDomain,
  UNLINKED_COLOR,
  widenRange,
  type AttributeValue,
  type NumericDomain,
  type NumericRange,
} from "./colorByPalette";
import type { AttributePalette, ColorBySettings } from "./colorBySettings";
import { PREVIEW_TABLE_NAME } from "$lib/stores/trackEditing";
import { BaseSchema } from "$lib/types/dataset";
import { paletteColorAt } from "$lib/utils/coreUtils";
import { buildTopEntityIdByEntityId } from "$lib/utils/entityHierarchy";

/**
 * Resolve the color of every object and annotation of a record, for the active "Color by" mode.
 *
 * - Entity mode: one palette color per top-level object, in the order objects were first met.
 * - Entity attribute: the color of the top-level object's value, on every shape of the object.
 * - Annotation attribute of table T: rows of T take their own value's color, rows of other
 *   tables the "no value" color; objects and tracks show the most frequent value of their rows
 *   of T (the mean for numbers). When T holds tracks, shapes take their track's value.
 *
 * Every color is `#rrggbb`. Drafts, previews and shapes of unknown objects get UNLINKED_COLOR.
 */

export type ActiveColorMode =
  | { readonly kind: "entity" }
  | { readonly kind: "attribute"; readonly attribute: ColorByAttribute };

export const ENTITY_MODE: ActiveColorMode = Object.freeze({ kind: "entity" });

/** The mode the settings select; an attribute the dataset no longer has falls back to Entity. */
export function resolveActiveMode(
  catalogue: ColorByCatalogue,
  settings: ColorBySettings,
): ActiveColorMode {
  if (settings.selected === ENTITY_COLOR_MODE) return ENTITY_MODE;
  const attribute = catalogue.byId.get(settings.selected);
  return attribute ? { kind: "attribute", attribute } : ENTITY_MODE;
}

/** Palette slots of top-level objects, in the order they were first met. Slots are never freed. */
export interface EntityColorOrder {
  slotOf(topEntityId: string): number;
}

export function createEntityColorOrder(): EntityColorOrder {
  const slots = new Map<string, number>();
  return {
    slotOf(topEntityId) {
      let slot = slots.get(topEntityId);
      if (slot === undefined) {
        slot = slots.size;
        slots.set(topEntityId, slot);
      }
      return slot;
    },
  };
}

export type ColorEntity = {
  readonly id: string;
  readonly data: { readonly parent_id?: unknown; readonly [key: string]: unknown };
};

export type ColorAnnotation = {
  readonly id: string;
  readonly table_info?: { readonly name: string; readonly base_schema: string };
  readonly data: {
    readonly entity_id?: unknown;
    readonly tracklet_id?: unknown;
    readonly [key: string]: unknown;
  };
};

/** Anything drawn for an annotation: a stored row, a display copy, an interpolated ghost. */
export type ColorTarget = {
  readonly id: string;
  readonly data?: { readonly entity_id?: unknown };
  readonly entityRef?: { readonly id: string };
  /** An interpolated ghost carries the keyframe it was interpolated from as `ui.startRef`. */
  readonly ui?: object;
};

export type AnnotationColorFn = (target: ColorTarget) => string;

export type LegendUnit = "objects" | "annotations" | "tracks";

export interface LegendEntry {
  readonly key: string;
  readonly color: string;
  readonly count: number;
  /** The user chose this color. */
  readonly custom: boolean;
}

export interface CategoricalLegend {
  readonly kind: "categorical";
  readonly attribute: ColorByAttribute;
  readonly unit: LegendUnit;
  /** The values of this record, in natural order, at most MAX_LEGEND_ENTRIES. */
  readonly entries: readonly LegendEntry[];
  /** Values of this record left out of `entries`. */
  readonly moreCount: number;
  /** Remembered values this record does not have. */
  readonly knownEntries: readonly LegendEntry[];
  /** Objects, annotations or tracks that have a value. */
  readonly itemCount: number;
  readonly noValueCount: number;
  /** Annotations of other tables, drawn in the "no value" color. */
  readonly otherCount: number;
  /** Values of this record that share their color with another one. */
  readonly sharedColorCount: number;
  readonly customized: boolean;
}

export interface NumericLegend {
  readonly kind: "numeric";
  readonly attribute: ColorByAttribute;
  readonly unit: LegendUnit;
  readonly domain: NumericDomain | null;
  /** The range of the values in this record. */
  readonly observed: NumericRange | null;
  readonly low: string;
  readonly high: string;
  readonly stops: readonly string[];
  readonly itemCount: number;
  readonly noValueCount: number;
  readonly otherCount: number;
  readonly customized: boolean;
}

export type ColorLegend = CategoricalLegend | NumericLegend;

/** What the settings should remember after this build: a longer order or a wider range. */
export interface PendingLearned {
  readonly attributeId: string;
  readonly order?: readonly string[];
  readonly seen?: NumericRange;
}

export interface ColorResolver {
  readonly mode: ActiveColorMode;
  /** The color of an object; a sub-entity resolves to its top-level object. */
  readonly colorOfEntity: (entityId: string) => string;
  readonly colorOfAnnotation: AnnotationColorFn;
  /** Null in Entity mode. */
  readonly legend: ColorLegend | null;
  readonly pendingLearned: PendingLearned | null;
}

export interface ColorResolverInput {
  readonly mode: ActiveColorMode;
  readonly palette: AttributePalette | undefined;
  readonly entities: readonly ColorEntity[];
  /** Only read for annotation attributes. */
  readonly annotations: readonly ColorAnnotation[];
  readonly entityOrder: EntityColorOrder;
}

export const MAX_LEGEND_ENTRIES = 200;
const RAMP_LEGEND_STOPS = 9;

const COLORABLE_BASE_SCHEMAS = new Set<string>([
  BaseSchema.BBox,
  BaseSchema.Mask,
  BaseSchema.MultiPath,
  BaseSchema.Keypoints,
  BaseSchema.TextSpan,
  BaseSchema.Tracklet,
]);
// The text annotator's temporary span lives in the annotations store under this table name.
const TEMPORARY_SPAN_TABLE = "not_a_table";
const UNDRAWN_TABLES = new Set([PREVIEW_TABLE_NAME, TEMPORARY_SPAN_TABLE]);
const EMPTY_COLORS: ReadonlyMap<string, string> = new Map();
const TRACKLET_BASE_SCHEMA: string = BaseSchema.Tracklet;

/** The stored row a target is drawn for: the start keyframe of a ghost, else the target itself. */
function storedRowId(target: ColorTarget): string {
  const startRef = (target.ui as { startRef?: { id?: unknown } } | undefined)?.startRef;
  return typeof startRef?.id === "string" ? startRef.id : target.id;
}

/** The object an annotation, a display copy or a keypoints shape belongs to. */
export function annotationEntityId(target: ColorTarget): string {
  const entityId = target.data?.entity_id;
  if (typeof entityId === "string" && entityId !== "") return entityId;
  return target.entityRef?.id ?? "";
}

/** The legend's palette part, from the values met in this build. */
interface Scale {
  colorOf(value: AttributeValue): string;
  /** Summary of several values: most frequent category (ties: earlier color), or the mean. */
  summarize(values: readonly (string | number)[]): AttributeValue;
  legend(counts: CountedValues, unit: LegendUnit, otherCount: number): ColorLegend;
  pending: PendingLearned | null;
}

interface CountedValues {
  /** Occurrences per category key, or every number. */
  readonly categories: ReadonlyMap<string, number>;
  readonly numbers: readonly number[];
  readonly noValueCount: number;
}

function countValues(values: Iterable<AttributeValue>): CountedValues {
  const categories = new Map<string, number>();
  const numbers: number[] = [];
  let noValueCount = 0;
  for (const value of values) {
    if (value === null) noValueCount++;
    else if (typeof value === "number") numbers.push(value);
    else categories.set(value, (categories.get(value) ?? 0) + 1);
  }
  return { categories, numbers, noValueCount };
}

function rangeOf(numbers: readonly number[]): NumericRange | null {
  if (numbers.length === 0) return null;
  let min = numbers[0];
  let max = numbers[0];
  for (const value of numbers) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return { min, max };
}

function categoricalScale(
  attribute: ColorByAttribute,
  palette: AttributePalette | undefined,
  observed: ReadonlyMap<string, number>,
): Scale {
  const order = extendCategoricalOrder(palette?.order, attribute.seeds, observed.keys());
  const slotByKey = new Map(order.map((key, index) => [key, index]));
  const overrides = palette?.colors;
  const colorOfKey = (key: string) => categoricalColor(key, slotByKey, overrides);
  const entryOf = (key: string, count: number): LegendEntry => ({
    key,
    color: colorOfKey(key),
    count,
    custom: !!overrides && Object.hasOwn(overrides, key),
  });

  return {
    colorOf: (value) => (value === null ? NO_VALUE_COLOR : colorOfKey(String(value))),
    summarize(values) {
      const counts = new Map<string, number>();
      for (const value of values) counts.set(String(value), (counts.get(String(value)) ?? 0) + 1);
      let best: string | null = null;
      let bestCount = 0;
      for (const [key, count] of counts) {
        if (count > bestCount || (count === bestCount && best !== null && ranksBefore(key, best))) {
          best = key;
          bestCount = count;
        }
      }
      return best;
    },
    legend(counts, unit, otherCount) {
      const keys = [...counts.categories.keys()].sort(compareValueKeys);
      const entries = keys.map((key) => entryOf(key, counts.categories.get(key) ?? 0));
      const colorUses = new Map<string, number>();
      for (const entry of entries)
        colorUses.set(entry.color, (colorUses.get(entry.color) ?? 0) + 1);
      const known = order.filter((key) => !counts.categories.has(key)).sort(compareValueKeys);
      let itemCount = 0;
      for (const count of counts.categories.values()) itemCount += count;
      return {
        kind: "categorical",
        attribute,
        unit,
        entries: entries.slice(0, MAX_LEGEND_ENTRIES),
        moreCount: Math.max(0, entries.length - MAX_LEGEND_ENTRIES),
        knownEntries: known.slice(0, MAX_LEGEND_ENTRIES).map((key) => entryOf(key, 0)),
        itemCount,
        noValueCount: counts.noValueCount,
        otherCount,
        sharedColorCount: entries.filter((entry) => (colorUses.get(entry.color) ?? 0) > 1).length,
        customized: !!overrides && Object.keys(overrides).length > 0,
      };
    },
    pending:
      order.length > (palette?.order?.length ?? 0) ? { attributeId: attribute.id, order } : null,
  };

  function ranksBefore(a: string, b: string): boolean {
    const slotA = slotByKey.get(a) ?? Number.POSITIVE_INFINITY;
    const slotB = slotByKey.get(b) ?? Number.POSITIVE_INFINITY;
    return slotA !== slotB ? slotA < slotB : compareValueKeys(a, b) < 0;
  }
}

function numericScale(
  attribute: ColorByAttribute,
  palette: AttributePalette | undefined,
  observed: NumericRange | null,
): Scale {
  const seen = attribute.fixedDomain ? undefined : widenRange(palette?.seen, observed);
  const domain = resolveNumericDomain(attribute.fixedDomain, seen);
  const ramp = createRamp(palette?.ramp?.low, palette?.ramp?.high);
  const colorOfNumber = (value: number) => ramp.colorAt(rampPosition(value, domain));

  return {
    colorOf: (value) => (typeof value === "number" ? colorOfNumber(value) : NO_VALUE_COLOR),
    summarize(values) {
      let sum = 0;
      let count = 0;
      for (const value of values) {
        if (typeof value !== "number") continue;
        sum += value;
        count++;
      }
      return count > 0 ? sum / count : null;
    },
    legend(counts, unit, otherCount) {
      return {
        kind: "numeric",
        attribute,
        unit,
        domain,
        observed: rangeOf(counts.numbers),
        low: ramp.low,
        high: ramp.high,
        stops: ramp.stops(RAMP_LEGEND_STOPS),
        itemCount: counts.numbers.length,
        noValueCount: counts.noValueCount,
        otherCount,
        customized: !!palette?.ramp,
      };
    },
    pending: seen && seen !== palette?.seen ? { attributeId: attribute.id, seen } : null,
  };
}

function scaleFor(
  attribute: ColorByAttribute,
  palette: AttributePalette | undefined,
  counts: CountedValues,
): Scale {
  return attribute.scale === "numeric"
    ? numericScale(attribute, palette, rangeOf(counts.numbers))
    : categoricalScale(attribute, palette, counts.categories);
}

interface Resolution {
  readonly entityColor: ReadonlyMap<string, string>;
  readonly annotationColor: ReadonlyMap<string, string>;
  readonly legend: ColorLegend | null;
  readonly pending: PendingLearned | null;
}

function topEntityIds(topIdOf: ReadonlyMap<string, string>): Set<string> {
  return new Set(topIdOf.values());
}

function resolveEntityAttribute(
  attribute: ColorByAttribute,
  palette: AttributePalette | undefined,
  entities: readonly ColorEntity[],
  topIdOf: ReadonlyMap<string, string>,
): Resolution {
  const valueByTop = new Map<string, AttributeValue>();
  for (const entity of entities) {
    // Top-level objects, and sub-entities whose parent is missing.
    if (topIdOf.get(entity.id) !== entity.id || valueByTop.has(entity.id)) continue;
    valueByTop.set(entity.id, readAttributeValue(attribute, entity.data[attribute.field]));
  }
  const counts = countValues(valueByTop.values());
  const scale = scaleFor(attribute, palette, counts);
  const entityColor = new Map<string, string>();
  for (const [topId, value] of valueByTop) entityColor.set(topId, scale.colorOf(value));
  return {
    entityColor,
    annotationColor: EMPTY_COLORS,
    legend: scale.legend(counts, "objects", 0),
    pending: scale.pending,
  };
}

function resolveAnnotationAttribute(
  attribute: ColorByAttribute,
  palette: AttributePalette | undefined,
  annotations: readonly ColorAnnotation[],
  topIdOf: ReadonlyMap<string, string>,
): Resolution {
  const attributeOnTracks = attribute.baseSchema === BaseSchema.Tracklet;
  const carrying: Array<{ id: string; value: AttributeValue; topId: string; trackId: string }> = [];
  const others: Array<{ id: string; isTrack: boolean; trackId: string }> = [];
  const visited = new Set<string>();

  for (const row of annotations) {
    const table = row.table_info?.name;
    const baseSchema = row.table_info?.base_schema;
    if (!table || !baseSchema || !COLORABLE_BASE_SCHEMAS.has(baseSchema)) continue;
    if (UNDRAWN_TABLES.has(table) || visited.has(row.id)) continue;
    const entityId = typeof row.data.entity_id === "string" ? row.data.entity_id : "";
    const topId = topIdOf.get(entityId);
    if (!topId) continue; // linked to no known object: drawn as unlinked
    visited.add(row.id);
    const trackId = typeof row.data.tracklet_id === "string" ? row.data.tracklet_id : "";
    if (table === attribute.table) {
      carrying.push({
        id: row.id,
        value: readAttributeValue(attribute, row.data[attribute.field]),
        topId,
        trackId,
      });
    } else {
      others.push({ id: row.id, isTrack: baseSchema === TRACKLET_BASE_SCHEMA, trackId });
    }
  }

  const counts = countValues(carrying.map((row) => row.value));
  const scale = scaleFor(attribute, palette, counts);
  const annotationColor = new Map<string, string>();
  const valuesByTop = new Map<string, Array<string | number>>();
  const valuesByTrack = new Map<string, Array<string | number>>();
  for (const row of carrying) {
    annotationColor.set(row.id, scale.colorOf(row.value));
    if (row.value === null) continue;
    pushTo(valuesByTop, row.topId, row.value);
    if (!attributeOnTracks && row.trackId) pushTo(valuesByTrack, row.trackId, row.value);
  }

  let otherCount = 0;
  for (const row of others) {
    if (attributeOnTracks) {
      // Shapes take the value of the track they belong to.
      const trackColor = row.trackId ? annotationColor.get(row.trackId) : undefined;
      if (trackColor) {
        annotationColor.set(row.id, trackColor);
        continue;
      }
    } else if (row.isTrack) {
      // A track shows the summary of its shapes.
      const values = valuesByTrack.get(row.id);
      annotationColor.set(row.id, values ? scale.colorOf(scale.summarize(values)) : NO_VALUE_COLOR);
      continue;
    }
    annotationColor.set(row.id, NO_VALUE_COLOR);
    otherCount++;
  }

  const entityColor = new Map<string, string>();
  for (const topId of topEntityIds(topIdOf)) {
    const values = valuesByTop.get(topId);
    entityColor.set(topId, values ? scale.colorOf(scale.summarize(values)) : NO_VALUE_COLOR);
  }

  return {
    entityColor,
    annotationColor,
    legend: scale.legend(counts, attributeOnTracks ? "tracks" : "annotations", otherCount),
    pending: scale.pending,
  };
}

function pushTo<V>(map: Map<string, V[]>, key: string, value: V): void {
  const values = map.get(key);
  if (values) values.push(value);
  else map.set(key, [value]);
}

// ─── Building, and reusing an equivalent resolver ────────────────────────────────

interface ResolverState {
  readonly modeKey: string;
  readonly topIdOf: ReadonlyMap<string, string>;
  readonly entityColor: ReadonlyMap<string, string>;
  readonly annotationColor: ReadonlyMap<string, string>;
  readonly legendKey: string;
  readonly pendingKey: string;
}

const resolverStates = new WeakMap<ColorResolver, ResolverState>();

function modeKey(mode: ActiveColorMode): string {
  return mode.kind === "entity"
    ? ENTITY_COLOR_MODE
    : `${mode.attribute.id}:${mode.attribute.scale}:${mode.attribute.fieldType}`;
}

function sameMap(a: ReadonlyMap<string, string>, b: ReadonlyMap<string, string>): boolean {
  if (a === b) return true;
  if (a.size !== b.size) return false;
  for (const [key, value] of a) {
    if (b.get(key) !== value) return false;
  }
  return true;
}

function sameState(a: ResolverState, b: ResolverState): boolean {
  return (
    a.modeKey === b.modeKey &&
    a.legendKey === b.legendKey &&
    a.pendingKey === b.pendingKey &&
    sameMap(a.topIdOf, b.topIdOf) &&
    sameMap(a.entityColor, b.entityColor) &&
    sameMap(a.annotationColor, b.annotationColor)
  );
}

/**
 * Resolve the colors of a record. Returns `previous` when every color, the legend and what is
 * left to remember are unchanged, so that a commit that changes no color re-renders nothing.
 */
export function buildColorResolver(
  input: ColorResolverInput,
  previous?: ColorResolver | null,
): ColorResolver {
  const { mode, palette, entities, annotations, entityOrder } = input;
  const topIdOf = buildTopEntityIdByEntityId(entities);

  // Every mode allocates entity slots, so Entity colors never depend on the modes used before.
  const slotColor = new Map<string, string>();
  for (const entity of entities) {
    if (entity.data.parent_id === "") {
      slotColor.set(entity.id, paletteColorAt(entityOrder.slotOf(entity.id)));
    }
  }

  let resolution: Resolution;
  if (mode.kind === "entity") {
    resolution = {
      entityColor: slotColor,
      annotationColor: EMPTY_COLORS,
      legend: null,
      pending: null,
    };
  } else if (mode.attribute.scope === "entity") {
    resolution = resolveEntityAttribute(mode.attribute, palette, entities, topIdOf);
  } else {
    resolution = resolveAnnotationAttribute(mode.attribute, palette, annotations, topIdOf);
  }

  const state: ResolverState = {
    modeKey: modeKey(mode),
    topIdOf,
    entityColor: resolution.entityColor,
    annotationColor: resolution.annotationColor,
    legendKey: JSON.stringify(resolution.legend),
    pendingKey: JSON.stringify(resolution.pending),
  };
  const previousState = previous ? resolverStates.get(previous) : undefined;
  if (previous && previousState && sameState(previousState, state)) return previous;

  const colorOfEntity = (entityId: string): string =>
    state.entityColor.get(state.topIdOf.get(entityId) ?? entityId) ?? UNLINKED_COLOR;
  const colorOfAnnotation: AnnotationColorFn = (target) =>
    state.annotationColor.get(storedRowId(target)) ?? colorOfEntity(annotationEntityId(target));

  const resolver: ColorResolver = {
    mode,
    colorOfEntity,
    colorOfAnnotation,
    legend: resolution.legend,
    pendingLearned: resolution.pending,
  };
  resolverStates.set(resolver, state);
  return resolver;
}
