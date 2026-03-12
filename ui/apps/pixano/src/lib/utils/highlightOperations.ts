/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
import {
  annotations,
  entities,
  highlightedEntity,
  newShape,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { ToolType } from "$lib/tools";
import { BaseSchema, Entity, Tracklet, type Annotation } from "$lib/types/dataset";

let fusionHighlightedEntityId: string | null = null;

function setEntityChildHighlight(
  entity: Entity | undefined,
  highlighted: "all" | "self" | "none",
): boolean {
  if (!entity?.ui.childs || entity.ui.childs.length === 0) return false;

  let hasChanged = false;
  for (const ann of entity.ui.childs) {
    if (ann.ui.displayControl.highlighted === highlighted) continue;
    ann.ui.displayControl = {
      ...ann.ui.displayControl,
      highlighted,
    };
    hasChanged = true;
  }
  return hasChanged;
}

function resolveActiveHighlightedEntity(entitiesList: Entity[]): string | null {
  if (fusionHighlightedEntityId) return fusionHighlightedEntityId;

  const activeEntity = entitiesList.find((entity) =>
    entity.ui.childs?.some((ann) => ann.ui.displayControl.highlighted === "self"),
  );
  fusionHighlightedEntityId = activeEntity?.id ?? null;
  return fusionHighlightedEntityId;
}

export const scrollIntoView = (entity_id: string) => {
  const cardElement = document.querySelector(`#card-object-${entity_id}`);
  if (!cardElement) return;

  requestAnimationFrame(() => {
    cardElement.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const trackElement = document
    .querySelector(`#video-object-${entity_id}`)
    ?.getElementsByClassName("video-tracklet");
  if (trackElement && trackElement.length > 0) {
    trackElement[0].scrollIntoView({ block: "center", inline: "center" });
  }
};

export const highlightEntity = (
  entity_id: string,
  isHighlighted: boolean,
  shouldAutoScroll = true,
): number => {
  const entitiesList = entities.value;
  const entitiesById = new Map(entitiesList.map((entity) => [entity.id, entity]));
  const targetEntity = entitiesById.get(entity_id);

  const maxFrameIndex = lastFrameIndex.value ?? currentFrameIndex.value;
  let trackStart = maxFrameIndex + 1;
  let trackEnd = 0;
  const selectedToolType = selectedTool.value?.type ?? ToolType.Pan;
  const useFastPanHighlight = selectedToolType === ToolType.Pan;
  const shouldUpdateFusionDisplayControl = selectedToolType === ToolType.Fusion;

  if (targetEntity?.ui.childs) {
    for (const ann of targetEntity.ui.childs) {
      if (!ann.is_type(BaseSchema.Tracklet)) continue;
      trackStart = Math.min(trackStart, (ann as Tracklet).data.start_frame);
      trackEnd = Math.max(trackEnd, (ann as Tracklet).data.end_frame);
    }
  }

  if (useFastPanHighlight) {
    highlightedEntity.value = isHighlighted ? null : entity_id;
    fusionHighlightedEntityId = null;
  } else if (shouldUpdateFusionDisplayControl && targetEntity) {
    highlightedEntity.value = null;
    annotations.update((objects) => {
      let hasChanged = false;
      const activeEntityId = resolveActiveHighlightedEntity(entitiesList);

      if (isHighlighted) {
        hasChanged = setEntityChildHighlight(targetEntity, "all");
        if (activeEntityId === entity_id) {
          fusionHighlightedEntityId = null;
        }
      } else {
        if (activeEntityId && activeEntityId !== entity_id) {
          hasChanged =
            setEntityChildHighlight(entitiesById.get(activeEntityId), "all") || hasChanged;
        }
        hasChanged = setEntityChildHighlight(targetEntity, "self") || hasChanged;
        fusionHighlightedEntityId = entity_id;
      }

      return hasChanged ? [...objects] : objects;
    });
  }

  // Auto-expand and scroll only when explicitly requested (e.g. selection from canvas/track).
  // Inspector list clicks pass shouldAutoScroll=false to avoid global list churn on selection.
  if (!isHighlighted && shouldAutoScroll) {
    entities.update((currentEntities) => {
      let hasChanged = false;
      for (const ent of currentEntities) {
        const shouldOpen = ent.id === entity_id;
        if ((ent.ui.displayControl.open ?? false) !== shouldOpen) {
          hasChanged = true;
          break;
        }
      }

      if (!hasChanged) return currentEntities;

      return currentEntities.map((ent) => {
        const shouldOpen = ent.id === entity_id;
        if ((ent.ui.displayControl.open ?? false) === shouldOpen) {
          return ent;
        }
        ent.ui.displayControl = { ...ent.ui.displayControl, open: shouldOpen };
        return ent;
      });
    });
    scrollIntoView(entity_id);
  }
  // Return frame index
  if (
    !isHighlighted &&
    trackStart <= trackEnd &&
    (currentFrameIndex.value <trackStart || currentFrameIndex.value > trackEnd)
  ) {
    return trackStart;
  } else {
    return currentFrameIndex.value;
  }
};

/**
 * Set highlight state for a specific set of annotation IDs.
 * Annotations not in the set are dimmed to "none" when dimRest is true,
 * or left unchanged when dimRest is false.
 */
export function highlightAnnotationIds(
  ids: Set<string>,
  dimRest: boolean = true,
  state: "self" | "all" | "none" = "self",
): void {
  annotations.update((anns) =>
    anns.map((ann) => {
      if (ids.has(ann.id)) {
        ann.ui.displayControl.highlighted = state;
      } else if (dimRest) {
        ann.ui.displayControl.highlighted = "none";
      }
      return ann;
    }),
  );
}

/**
 * Set highlight+editing for annotations matching a predicate,
 * dim+not-editing for the rest.
 */
export function highlightWithEditing(predicate: (ann: Annotation) => boolean): void {
  highlightedEntity.value = null;
  annotations.update((anns) =>
    anns.map((ann) => {
      const shouldHighlight = predicate(ann);
      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        highlighted: shouldHighlight ? "self" : "none",
        editing: shouldHighlight,
      };
      return ann;
    }),
  );
}

/**
 * Highlight a tracklet and all its children as "self", dim everything else.
 */
export function highlightTrackletChildren(tracklet: Tracklet): void {
  const ids = new Set([tracklet.id, ...(tracklet.ui.childs ?? []).map((ann) => ann.id)]);
  highlightedEntity.value = null;
  highlightAnnotationIds(ids, true);
}

export const clearHighlighting = () => {
  fusionHighlightedEntityId = null;
  highlightedEntity.value = null;
  //deselect everything = unhighlight all and stop editing
  newShape.value = { status: "none" };
  annotations.update((anns) =>
    anns.map((ann) => {
      ann.ui.displayControl = { ...ann.ui.displayControl, editing: false, highlighted: "all" };
      return ann;
    }),
  );
};
