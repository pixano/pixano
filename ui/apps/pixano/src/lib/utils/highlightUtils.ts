/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "$lib/tools";
import type { Annotation, Entity } from "$lib/types/dataset";

export type HighlightState = "all" | "self" | "none";

/**
 * Walk up the parent chain to find the root (top-level) entity id.
 */
export function getTopEntityId(annotation: Annotation, entitiesById: Map<string, Entity>): string {
  const topEntityId = annotation.ui.top_entities?.[0]?.id;
  if (topEntityId) return topEntityId;

  let entityId = annotation.data.entity_id;
  let entity = entitiesById.get(entityId);
  while (entity && entity.data.parent_id !== "") {
    entityId = entity.data.parent_id;
    entity = entitiesById.get(entityId);
  }
  return entityId;
}

/**
 * Compute effective highlight state for an annotation, taking into account
 * the currently focused entity and the active tool.
 */
export function getEffectiveHighlight(
  annotation: Annotation,
  focusedEntityId: string | null,
  selectedToolType: ToolType,
  entitiesById: Map<string, Entity> | null,
): HighlightState {
  const currentHighlight = annotation.ui.displayControl.highlighted;
  if (selectedToolType !== ToolType.Pan || !focusedEntityId || entitiesById === null) {
    return currentHighlight;
  }
  // In Pan mode, a focused entity should visually stand out in context:
  // selected entity = self, every other entity = neutral (none).
  return getTopEntityId(annotation, entitiesById) === focusedEntityId ? "self" : "none";
}
