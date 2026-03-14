/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import { currentItemId } from "./videoStores.svelte";
import { entities, highlightedEntity } from "./workspaceStores.svelte";
import { entityHasTracklets } from "$lib/types/dataset";

const MAX_PINNED_TIMELINE_ENTITIES = 2;

export const pinnedTimelineEntityIds = reactiveStore<string[]>([]);

export const timelineFocusEntityIds = reactiveDerived<string[]>(() => {
  const validEntityIds = new Set(
    entities.value
      .filter((entity) => entityHasTracklets(entity) && !entity.ui.displayControl.hidden)
      .map((entity) => entity.id),
  );

  const focusedEntityId = highlightedEntity.value;
  const pinnedIds = pinnedTimelineEntityIds.value.filter(
    (entityId): entityId is string =>
      Boolean(entityId) && entityId !== focusedEntityId && validEntityIds.has(entityId),
  );

  return [focusedEntityId, ...pinnedIds].filter(
    (entityId): entityId is string => Boolean(entityId) && validEntityIds.has(entityId),
  );
});

export function togglePinnedTimelineEntity(entityId: string): void {
  pinnedTimelineEntityIds.update((currentIds) => {
    if (currentIds.includes(entityId)) {
      return currentIds.filter((id) => id !== entityId);
    }

    return [entityId, ...currentIds].slice(0, MAX_PINNED_TIMELINE_ENTITIES);
  });
}

export function clearPinnedTimelineEntities(): void {
  pinnedTimelineEntityIds.value = [];
}

export function isTimelineEntityPinned(entityId: string): boolean {
  return pinnedTimelineEntityIds.value.includes(entityId);
}

$effect.root(() => {
  let lastItemId = "";

  $effect(() => {
    const itemId = currentItemId.value;
    if (itemId === lastItemId) return;
    lastItemId = itemId;
    clearPinnedTimelineEntities();
  });
});
