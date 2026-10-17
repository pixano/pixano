/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Pure helpers for pointer and keyboard interaction with boxes on the canvas: which box
 * is under the pointer, how a box is identified from frame to frame, what the E key acts
 * on, and where the box action chip is anchored.
 */

import { PREVIEW_TABLE_NAME } from "$lib/stores/trackEditing";

/** A box as displayed on the canvas: coords are `[x, y, width, height]` in image pixels. */
export type BoxLike = {
  id: string;
  data: { coords: number[]; view_name: string; tracklet_id?: string };
  table_info?: { name?: string };
  ui: { displayControl: { hidden?: boolean; editing?: boolean; highlighted?: string } };
};

export type Point = { x: number; y: number };
export type Rect = { x: number; y: number; width: number; height: number };

/** A box drawn by a tracking session or a detection review, not a stored annotation. */
export function isPreviewBox(box: BoxLike): boolean {
  return box.table_info?.name === PREVIEW_TABLE_NAME;
}

/** Whether the user can point at, select and edit the box. */
export function isInteractiveBox(box: BoxLike): boolean {
  return !box.ui.displayControl.hidden && !isPreviewBox(box);
}

/** Whether `point` lies in the box, edges included (negative sizes are tolerated). */
export function boxContainsPoint(box: BoxLike, point: Point): boolean {
  const [x, y, width, height] = box.data.coords;
  const left = Math.min(x, x + width);
  const right = Math.max(x, x + width);
  const top = Math.min(y, y + height);
  const bottom = Math.max(y, y + height);
  return point.x >= left && point.x <= right && point.y >= top && point.y <= bottom;
}

/**
 * The box a pointer at `point` acts on: the smallest interactive box containing it, so a
 * small box nested in a larger one stays reachable. Equal areas go to the box being
 * edited, then to the later one in `boxes` (drawn on top).
 */
export function pickBoxAtPoint<T extends BoxLike>(
  boxes: ReadonlyArray<T>,
  point: Point,
): T | undefined {
  let best: T | undefined;
  let bestArea = Infinity;
  for (const box of boxes) {
    if (!isInteractiveBox(box) || !boxContainsPoint(box, point)) continue;
    const area = Math.abs(box.data.coords[2] * box.data.coords[3]);
    const wins =
      best === undefined ||
      area < bestArea ||
      (area === bestArea &&
        (Boolean(box.ui.displayControl.editing) || !best.ui.displayControl.editing));
    if (wins) {
      best = box;
      bestArea = area;
    }
  }
  return best;
}

/**
 * Identifies a box from frame to frame: a track's box is keyed by its track, whether it
 * is a keyframe or an interpolated box whose id changes on every frame.
 */
export function boxStableKey(box: BoxLike): string {
  const trackletId = box.data.tracklet_id;
  return trackletId ? `track:${trackletId}` : `box:${box.id}`;
}

export function findBoxByStableKey<T extends BoxLike>(
  boxes: ReadonlyArray<T>,
  key: string | null,
): T | undefined {
  if (key === null) return undefined;
  return boxes.find((box) => isInteractiveBox(box) && boxStableKey(box) === key);
}

/** The minimal Konva node API needed to find a node's view. */
export type NodeLike = { id(): string; getParent(): NodeLike | null };

export const ACTIVE_VIEW_GROUP_PREFIX = "active-";

/** The view a Konva node is drawn in, from its `active-<view>` ancestor group. */
export function viewNameOfNode(node: NodeLike | null): string | undefined {
  for (let current = node; current; current = current.getParent()) {
    const id = current.id();
    if (id.startsWith(ACTIVE_VIEW_GROUP_PREFIX)) return id.slice(ACTIVE_VIEW_GROUP_PREFIX.length);
  }
  return undefined;
}

/** The E key without modifiers or key repeat. */
export function isEditToggleKey(event: {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  repeat: boolean;
}): boolean {
  return (
    (event.key === "e" || event.key === "E") &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    !event.repeat
  );
}

/**
 * The box the E key toggles: the box under the pointer (or under the chip the pointer is
 * on), else a box of the focused entity (highlighted "self"), preferring the one being
 * edited, then the one in the pointer's view, then the first in view order.
 */
export function resolveKeyboardEditTarget<T extends BoxLike>(
  boxes: ReadonlyArray<T>,
  options: {
    pointedKey: string | null;
    pointerView?: string;
    viewOrder: ReadonlyArray<string>;
  },
): T | undefined {
  const pointed = findBoxByStableKey(boxes, options.pointedKey);
  if (pointed) return pointed;
  const focused = boxes.filter(
    (box) => isInteractiveBox(box) && box.ui.displayControl.highlighted === "self",
  );
  const edited = focused.find((box) => box.ui.displayControl.editing);
  if (edited) return edited;
  const inPointerView = focused.find((box) => box.data.view_name === options.pointerView);
  if (inPointerView) return inPointerView;
  const rank = (box: T) => {
    const index = options.viewOrder.indexOf(box.data.view_name);
    return index < 0 ? options.viewOrder.length : index;
  };
  return focused.reduce<T | undefined>(
    (best, box) => (best === undefined || rank(box) < rank(best) ? box : best),
    undefined,
  );
}

/** Cursor over a box: move over the edited box, pointer over a box that can be picked. */
export function computeBoxHoverCursor(hovered: BoxLike | undefined): string | null {
  if (!hovered) return null;
  return hovered.ui.displayControl.editing ? "move" : "pointer";
}

/**
 * Where the action chip attaches: the top-right corner of the part of the box that is
 * visible in the canvas (client coordinates), or null when the box is entirely outside.
 */
export function chipAnchorPoint(box: Rect, container: Rect): Point | null {
  const left = Math.max(box.x, container.x);
  const right = Math.min(box.x + box.width, container.x + container.width);
  const top = Math.max(box.y, container.y);
  const bottom = Math.min(box.y + box.height, container.y + container.height);
  if (right < left || bottom < top) return null;
  return { x: right, y: top };
}
