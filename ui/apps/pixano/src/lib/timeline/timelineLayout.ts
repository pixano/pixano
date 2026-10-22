/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The vertical layout of the timeline body, the rows under the sticky ruler, in body px (0 is
 * the top of the first row). Each slot owns the gap above its content, so a sticky header
 * cell can cover its whole block and no gap lets the lanes show through the header column.
 */

/** The gap above each slot's content, in px. */
export const ROW_GAP = 4;

/** What a slot of the timeline body holds. */
export type SlotKind = "session" | "detection" | "entity" | "view";

/** The content height of each kind of slot, without its gap, in px. */
export const SLOT_CONTENT_HEIGHT: Readonly<Record<SlotKind, number>> = {
  session: 28,
  detection: 20,
  entity: 36,
  view: 28,
};

/** A slot to lay out; `key` names it in the layout. */
export interface SlotInput {
  readonly key: string;
  readonly kind: SlotKind;
}

/** A laid-out slot: its block spans `[top, top + height)`. */
export interface Slot {
  readonly key: string;
  readonly kind: SlotKind;
  readonly top: number;
  /** ROW_GAP plus the content height. */
  readonly height: number;
  /** top + ROW_GAP. */
  readonly contentTop: number;
}

/** The slots, stacked from the top of the body. */
export interface TimelineLayout {
  readonly slots: readonly Slot[];
  /** The height of all the slots. */
  readonly height: number;
  /** The index of each key's slot (its first one, should a key repeat). */
  readonly indexByKey: ReadonlyMap<string, number>;
}

/** A vertical range of the body, `[y0, y1)`. */
export interface VerticalRange {
  readonly y0: number;
  readonly y1: number;
}

const MIN_WINDOW_STEP = 80;

// A measured length or scroll offset; 0 before the first measurement and when negative.
function measured(length: number): number {
  return length > 0 && Number.isFinite(length) ? length : 0;
}

/** The slots stacked from 0, in input order. */
export function buildTimelineLayout(inputs: readonly SlotInput[]): TimelineLayout {
  const slots: Slot[] = [];
  const indexByKey = new Map<string, number>();
  let top = 0;
  for (const { key, kind } of inputs) {
    const height = ROW_GAP + SLOT_CONTENT_HEIGHT[kind];
    if (!indexByKey.has(key)) indexByKey.set(key, slots.length);
    slots.push({ key, kind, top, height, contentTop: top + ROW_GAP });
    top += height;
  }
  return { slots, height: top, indexByKey };
}

/** The index of the slot whose block holds `y` (a gap belongs to the slot below it), or -1. */
export function slotAtY(layout: TimelineLayout, y: number): number {
  if (!(y >= 0 && y < layout.height)) return -1;
  const { slots } = layout;
  let low = 0;
  let high = slots.length - 1;
  while (low < high) {
    const mid = (low + high + 1) >>> 1;
    if (slots[mid].top <= y) low = mid;
    else high = mid - 1;
  }
  return low;
}

/** The height of the filler that closes the header column down to the body viewport's bottom. */
export function fillerHeight(layout: TimelineLayout, bodyViewportHeight: number): number {
  return Math.max(0, measured(bodyViewportHeight) - layout.height);
}

/** The scroll distance between two vertical render windows: half the viewport, at least 80 px. */
export function verticalWindowStep(viewportHeight: number): number {
  return Math.max(MIN_WINDOW_STEP, Math.round(measured(viewportHeight) / 2));
}

/** The vertical render window of a scroll position; it changes once per step of scrolling. */
export function verticalWindowIndex(scrollTop: number, viewportHeight: number): number {
  return Math.floor(measured(scrollTop) / verticalWindowStep(viewportHeight));
}

/**
 * The range whose rows draw their marks for a window: it reaches at least two steps above the
 * viewport and more than one step below it, wherever the scroll stands in the window.
 */
export function verticalRenderRange(index: number, viewportHeight: number): VerticalRange {
  const step = verticalWindowStep(viewportHeight);
  return { y0: (index - 2) * step, y1: (index + 2) * step + measured(viewportHeight) };
}

/** Whether a slot's block overlaps a range (touching an end is not enough). */
export function slotInRange(
  slot: { readonly top: number; readonly height: number },
  range: VerticalRange,
): boolean {
  return slot.top < range.y1 && slot.top + slot.height > range.y0;
}

/**
 * The scroll that shows a slot's whole block in the body viewport (the scroller's height minus
 * the sticky ruler), moving the least: the block's top when it is above the viewport or
 * taller than it, its bottom at the viewport's bottom when it is below; null when it shows.
 */
export function revealScrollTop(
  slot: { readonly top: number; readonly height: number },
  scrollTop: number,
  viewportHeight: number,
): number | null {
  const scroll = measured(scrollTop);
  const viewport = measured(viewportHeight);
  const bottom = slot.top + slot.height;
  if (slot.top >= scroll && bottom <= scroll + viewport) return null;
  if (slot.top < scroll || slot.height > viewport) return slot.top;
  return bottom - viewport;
}
