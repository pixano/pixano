/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { GridItemHTMLElement, GridStack } from "gridstack";

import type { WidgetLayout } from "$lib/extensions/types.js";

/**
 * Layout persistence seam. `WorkspaceManager` satisfies this, but the reflow
 * helpers depend only on this narrow surface so they can be unit-tested against
 * a real (headless) GridStack without pulling in the whole manager.
 */
export interface LayoutSink {
  updateLayout(id: string, layout: Partial<WidgetLayout>): void;
}

/**
 * Attach `element` as a grid widget. It keeps its stored position when that spot
 * is still free; if the spot is now taken (e.g. a widget being shown again after
 * others compacted into its slot) GridStack drops it in the next available spot
 * at the same size. When GridStack chooses the position, it is written back
 * through `sink` so the stored layout matches what is on screen.
 *
 * `element` must already be a child of `grid.el`.
 */
export function placeWidget(
  grid: GridStack,
  element: HTMLElement,
  widgetId: string,
  layout: WidgetLayout,
  minW: number,
  minH: number,
  sink: LayoutSink,
): GridItemHTMLElement {
  const { x, y, w, h } = layout;
  const spotIsFree = grid.isAreaEmpty(x, y, w, h);
  const placed = grid.makeWidget(
    element,
    spotIsFree ? { x, y, w, h, minH, minW } : { autoPosition: true, w, h, minH, minW },
  );
  // Persist the resolved position unconditionally: even when we ask for the stored
  // spot GridStack may clamp it (e.g. x+w past the column count), so the manager
  // must reflect what actually landed on screen. Grid = single source of truth.
  writeBack(widgetId, placed, sink);
  return placed;
}

/**
 * Fill the gap left by a hidden widget without resizing anything, then persist
 * the shifted positions. `compact` moves items programmatically, so GridStack's
 * user-drag persistence path never observes them — hence the explicit sync.
 */
export function fillGapAndSync(grid: GridStack, sink: LayoutSink): void {
  grid.compact("compact");
  syncLayouts(grid, sink);
}

/** Write every current grid item's position back through `sink`. */
export function syncLayouts(grid: GridStack, sink: LayoutSink): void {
  for (const element of grid.getGridItems()) {
    const widgetId = element.dataset.widgetId;
    if (widgetId) writeBack(widgetId, element, sink);
  }
}

function writeBack(widgetId: string, element: GridItemHTMLElement, sink: LayoutSink): void {
  const node = element.gridstackNode;
  if (!node) return;
  sink.updateLayout(widgetId, { x: node.x, y: node.y, w: node.w, h: node.h });
}
