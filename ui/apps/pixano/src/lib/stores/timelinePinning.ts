/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { entityHasTracklets, type Entity } from "$lib/types/dataset";

/** Entities whose tracklets can be shown in the timeline: tracked and not hidden. */
export function pinnableTimelineEntityIds(entities: readonly Entity[]): string[] {
  return entities
    .filter((entity) => entityHasTracklets(entity) && !entity.ui.displayControl.hidden)
    .map((entity) => entity.id);
}

/**
 * Toggle `entityId` in the pinned list; a newly pinned entity goes first. There is
 * no cap: "pin all" would make one meaningless, and the rows cost what they cost.
 */
export function togglePinnedId(ids: readonly string[], entityId: string): string[] {
  return ids.includes(entityId) ? ids.filter((id) => id !== entityId) : [entityId, ...ids];
}
