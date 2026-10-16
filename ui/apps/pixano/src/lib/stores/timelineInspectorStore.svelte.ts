/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import { pinnableTimelineEntityIds, togglePinnedId } from "./timelinePinning";
import { currentItemId } from "./videoStores.svelte";
import { entities, highlightedEntity } from "./workspaceStores.svelte";

export const pinnedTimelineEntityIds = reactiveStore<string[]>([]);

export const timelineFocusEntityIds = reactiveDerived<string[]>(() => {
  const validEntityIds = new Set(pinnableTimelineEntityIds(entities.value));

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
  pinnedTimelineEntityIds.update((currentIds) => togglePinnedId(currentIds, entityId));
}

export function clearPinnedTimelineEntities(): void {
  pinnedTimelineEntityIds.value = [];
}

export function pinAllTimelineEntities(): void {
  pinnedTimelineEntityIds.value = pinnableTimelineEntityIds(entities.value);
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
