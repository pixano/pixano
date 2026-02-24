/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
import { annotations, entities, newShape, selectedTool } from "$lib/stores/workspaceStores.svelte";
import { ToolType } from "$lib/tools";
import { BaseSchema, Track } from "$lib/types/dataset";
import { getTopEntity } from "$lib/utils/entityLookupUtils";

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

export const highlightEntity = (entity_id: string, isHighlighted: boolean): number => {
  let trackStart = lastFrameIndex.value + 1;
  let trackEnd = 0;
  const shouldUpdateDisplayControl =
    selectedTool.value.type === ToolType.Pan || selectedTool.value.type === ToolType.Fusion;

  annotations.update((objects) => {
    if (!shouldUpdateDisplayControl) {
      for (const ann of objects) {
        const topEntityId = getTopEntity(ann).id;
        if (topEntityId === entity_id && ann.is_type(BaseSchema.Tracklet)) {
          trackStart = Math.min(trackStart, (ann as Track).data.start_frame);
          trackEnd = Math.max(trackEnd, (ann as Track).data.end_frame);
        }
      }
      return objects;
    }

    const nextObjects = [...objects];
    let hasChanged = false;

    for (let i = 0; i < objects.length; i += 1) {
      const ann = objects[i];
      const topEntityId = getTopEntity(ann).id;

      if (topEntityId === entity_id && ann.is_type(BaseSchema.Tracklet)) {
        trackStart = Math.min(trackStart, (ann as Track).data.start_frame);
        trackEnd = Math.max(trackEnd, (ann as Track).data.end_frame);
      }

      const nextHighlight = isHighlighted ? "all" : topEntityId === entity_id ? "self" : "none";
      if (ann.ui.displayControl.highlighted === nextHighlight) {
        continue;
      }

      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        highlighted: nextHighlight,
      };
      nextObjects[i] = ann;
      hasChanged = true;
    }

    return hasChanged ? nextObjects : objects;
  });
  // Auto-expand the entity card and scroll it into view
  if (!isHighlighted) {
    entities.update((ents) => {
      let hasChanged = false;
      for (const ent of ents) {
        const shouldOpen = ent.id === entity_id;
        if ((ent.ui.displayControl.open ?? false) !== shouldOpen) {
          hasChanged = true;
          break;
        }
      }

      if (!hasChanged) return ents;

      return ents.map((ent) => {
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
    (currentFrameIndex.value < trackStart || currentFrameIndex.value > trackEnd)
  ) {
    return trackStart;
  } else {
    return currentFrameIndex.value;
  }
};

export const clearHighlighting = () => {
  //deselect everything = unhighlight all and stop editing
  newShape.value = { status: "none" };
  annotations.update((anns) =>
    anns.map((ann) => {
      ann.ui.displayControl = { ...ann.ui.displayControl, editing: false, highlighted: "all" };
      return ann;
    }),
  );
};
