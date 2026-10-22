/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The timeline's cameras: how many of them see an object, which lane the keyframe tools
 * follow, and the "+ Add in this view" flow that arms the box tool for an object in a camera.
 */

import { rowKeyframeLabel } from "./timelineRows";
import { EMPTY_LANE } from "./trackModel";
import type { EntityTrackModel, LaneGeom } from "./types";
import { ToolType } from "$lib/types/tools";

/** The cameras with a track of an object, in the record's order, and the "n/N views" label. */
export function cameraCoverage(
  presentViews: Iterable<string>,
  viewOrder: readonly string[],
): { present: string[]; total: number; label: string } {
  const present = new Set(presentViews);
  const inOrder = viewOrder.filter((view) => present.has(view));
  return {
    present: inOrder,
    total: viewOrder.length,
    label: `${inOrder.length}/${viewOrder.length} views`,
  };
}

/**
 * The camera the keyframe buttons, the selected keyframe and a retime follow on the selected
 * row, or null for all its cameras: the view shown alone, else the active camera when the row
 * is expanded into cameras.
 */
export function keyframeScopeView({
  viewCount,
  viewFilter,
  expanded,
  activeCamera,
}: {
  viewCount: number;
  viewFilter: string | null;
  expanded: boolean;
  activeCamera: string | null;
}): string | null {
  if (viewFilter !== null) return viewFilter;
  if (viewCount > 1 && expanded) return activeCamera;
  return null;
}

/** A stored camera that still belongs to the record, else `fallback`. */
export function resolveViewChoice(
  stored: string | null,
  viewOrder: readonly string[],
  fallback: string | null,
): string | null {
  return stored !== null && viewOrder.includes(stored) ? stored : fallback;
}

/**
 * What an object row's header says after the name: its keyframes in the camera shown alone
 * ("—" when that camera has no track of it), how many cameras see it in a multi-camera
 * record, its keyframes otherwise.
 */
export function rowHeaderMeta(
  model: EntityTrackModel,
  { viewOrder, viewFilter }: { viewOrder: readonly string[]; viewFilter: string | null },
): string {
  if (viewFilter !== null) {
    const lane = model.byView.get(viewFilter);
    return lane ? rowKeyframeLabel(lane.frames.length) : "—";
  }
  if (viewOrder.length > 1) return cameraCoverage(model.byView.keys(), viewOrder).label;
  return rowKeyframeLabel(model.union.frames.length);
}

/**
 * The layout key of an object's camera row. The unit separator keeps it apart from every
 * object id, "::" and the like included.
 */
export function cameraRowKey(entityId: string, view: string): string {
  return `${entityId}\u001f${view}`;
}

/** The DOM id of an object's camera rows, safe for an IDREF whatever the object id. */
export function cameraRowsDomId(entityId: string): string {
  return `timeline-cameras-${encodeURIComponent(entityId)}`;
}

/** An object's lane for a camera (empty when the camera has no track of it), or merged for null. */
export function scopedLane(model: EntityTrackModel, view: string | null): LaneGeom {
  if (view === null) return model.union;
  return model.byView.get(view) ?? EMPTY_LANE;
}

/** An entry of the save form's object list. */
export interface RelinkChoice {
  id: string;
  kind: "new" | "move" | "merge" | "forbidden";
}

/**
 * The object the save form's list shows selected. On its first run it is `preselectId` (the
 * object armed with "+ Add in this view") when the list offers it, else the first entry
 * ("new"). Later, the user's choice stays while it is still offered.
 */
export function nextRelinkSelection(
  choices: readonly RelinkChoice[],
  current: string | null,
  preselectId: string | null,
  firstRun: boolean,
): string {
  const usable = (id: string | null) =>
    id !== null && choices.some((choice) => choice.id === id && choice.kind !== "forbidden");
  if (!firstRun && usable(current)) return current;
  if (usable(preselectId)) return preselectId;
  return choices[0]?.id ?? "new";
}

/** An object armed for drawing in a camera ("+ Add in this view"). */
export interface AddInViewTarget {
  entityId: string;
  viewName: string;
}

export type ArmingSignal =
  | { type: "tool"; toolType: ToolType; tracking: boolean }
  | { type: "save-closed"; tracking: boolean }
  | { type: "record" }
  | { type: "entities"; ids: ReadonlySet<string> };

/**
 * What becomes of an armed target: it lasts while the box tool (or the tracking session it
 * started) is on, and goes when the save form closes on an ended session, the record changes
 * or the object is gone. Cancelling the form goes back to a running session: the target stays.
 */
export function nextArming(
  target: AddInViewTarget | null,
  signal: ArmingSignal,
): AddInViewTarget | null {
  if (target === null) return null;
  switch (signal.type) {
    case "tool":
      return signal.toolType === ToolType.Rectangle || signal.tracking ? target : null;
    case "save-closed":
      return signal.tracking ? target : null;
    case "entities":
      return signal.ids.has(target.entityId) ? target : null;
    default:
      return null;
  }
}

/** Whether an object can be added in a camera: only top-level objects can be picked in the save form. */
export function canAddInView(entity: {
  parentId: string | null;
  isConversation?: boolean;
}): boolean {
  return !entity.parentId && !entity.isConversation;
}
