/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { GRID_TOTAL_COLS, planViewportLayouts, type Viewport } from "./layoutPlanner.js";
import type { WidgetInstance, WidgetLayout } from "$lib/extensions/types.js";

/**
 * Domain of the "remember how I arranged this dataset" feature.
 *
 * A dataset's records all expose the *same* declared views (`camera_front`,
 * `lidar`, …), so the arrangement a user builds on one record is meaningful
 * for every other record of that dataset. This module owns the value object
 * describing that arrangement plus the two pure transforms around it:
 *
 *   - `snapshotDatasetLayout` — current widgets → storable preference,
 *   - `resolveRecordLayouts`  — stored preference + the views a record
 *                               actually has → the layout for each widget.
 *
 * Persistence itself lives in `datasetLayoutRepository.ts`; nothing here
 * touches storage, so the rules stay testable without a DOM.
 *
 * The view name is the key because it is the only widget identifier stable
 * across records: instance ids are minted per load, and titles are display
 * text an extension may localize or rewrite.
 */

/**
 * Shape version of a stored preference. Bump it whenever the persisted
 * structure changes; payloads carrying any other version are discarded on
 * read rather than migrated, so a stale entry degrades to "no preference"
 * instead of corrupting a workspace.
 */
export const DATASET_LAYOUT_VERSION = 1;

/** The arrangement remembered for a single dataset view. */
export interface StoredViewLayout {
  layout: WidgetLayout;
  hidden: boolean;
}

/** Everything remembered for one dataset, keyed by view name. */
export interface DatasetLayout {
  version: number;
  views: Record<string, StoredViewLayout>;
}

/** A widget's placement for the record being opened. */
export interface ResolvedLayout {
  layout: WidgetLayout;
  hidden: boolean;
}

/**
 * Capture the user's current arrangement as a storable preference.
 *
 * Only view-backed widgets are captured: a widget dragged in from the
 * palette has no counterpart in the next record's views, so there would be
 * nothing to restore it onto. Returns `null` when there is nothing worth
 * remembering, which callers treat as "no preference to write" rather than
 * "erase what is stored".
 */
export function snapshotDatasetLayout(widgets: readonly WidgetInstance[]): DatasetLayout | null {
  const views: Record<string, StoredViewLayout> = {};
  let captured = 0;
  let visible = 0;

  for (const widget of widgets) {
    if (!widget.viewName) continue;
    const hidden = widget.hidden === true;
    views[widget.viewName] = { layout: { ...widget.layout }, hidden };
    captured++;
    if (!hidden) visible++;
  }

  // A workspace with every view hidden is a transient state, not an arrangement
  // worth replaying: remembering it would open every other record of the
  // dataset on an empty grid, which reads as a failed load. The previously
  // stored arrangement stays instead.
  if (captured === 0 || visible === 0) return null;

  return { version: DATASET_LAYOUT_VERSION, views };
}

/**
 * Express a record's resolved placement as a replayable arrangement, so the
 * state a record opened in can be restored after the user rearranges it.
 */
export function toDatasetLayout(
  viewNames: readonly string[],
  layouts: readonly ResolvedLayout[],
): DatasetLayout {
  const views: Record<string, StoredViewLayout> = {};

  viewNames.forEach((viewName, index) => {
    views[viewName] = { layout: { ...layouts[index].layout }, hidden: layouts[index].hidden };
  });

  return { version: DATASET_LAYOUT_VERSION, views };
}

/**
 * Decide where each of a record's widgets goes.
 *
 * A view the user has arranged keeps that arrangement; any other view falls
 * back to the automatic placement computed for the record's widget count. A
 * fallback slot can collide with a remembered one (the stored arrangement was
 * built from a different set of views) — that is left to GridStack, which drops
 * a colliding widget into the next free spot at the requested size.
 */
export function resolveRecordLayouts(
  viewNames: readonly string[],
  viewport: Viewport,
  saved: DatasetLayout | null,
): ResolvedLayout[] {
  const planned = planViewportLayouts(viewNames.length, viewport);

  return viewNames.map((viewName, index) => {
    const stored = saved?.views[viewName];
    if (stored) return { layout: { ...stored.layout }, hidden: stored.hidden };
    return { layout: planned[index], hidden: false };
  });
}

/**
 * Validate an untrusted payload (hand-edited storage, an entry written by an
 * older build) into a `DatasetLayout`, or `null` when it cannot be trusted.
 * Unreadable views are dropped individually so one bad entry does not throw
 * away an otherwise usable arrangement.
 */
export function parseDatasetLayout(raw: unknown): DatasetLayout | null {
  if (!isRecord(raw)) return null;
  if (raw.version !== DATASET_LAYOUT_VERSION) return null;
  if (!isRecord(raw.views)) return null;

  const views: Record<string, StoredViewLayout> = {};
  for (const [viewName, entry] of Object.entries(raw.views)) {
    const parsed = parseStoredViewLayout(entry);
    if (parsed) views[viewName] = parsed;
  }

  return Object.keys(views).length > 0 ? { version: DATASET_LAYOUT_VERSION, views } : null;
}

/**
 * Accept only geometry the grid can actually honour. Storage is user-editable,
 * so a fractional, negative or over-wide cell would otherwise reach GridStack
 * and break the whole grid rather than just its own widget.
 */
function parseStoredViewLayout(entry: unknown): StoredViewLayout | null {
  if (!isRecord(entry) || !isRecord(entry.layout)) return null;

  const { x, y, w, h } = entry.layout;
  if (!isCellOffset(x) || !isCellOffset(y)) return null;
  // Rows are unbounded (a tall viewport plans widgets taller than the grid is
  // wide), so only the horizontal span is checked against the column count.
  if (!isCellSpan(w) || !isCellSpan(h)) return null;
  if (x + w > GRID_TOTAL_COLS) return null;

  return { layout: { x, y, w, h }, hidden: entry.hidden === true };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Grid coordinates are whole, non-negative cell offsets. */
function isCellOffset(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

/** A span covers at least one whole cell. */
function isCellSpan(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1;
}
