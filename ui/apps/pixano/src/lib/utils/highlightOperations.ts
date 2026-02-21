/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "$lib/tools";
import { BaseSchema, Tracklet } from "$lib/types/dataset";

import {
  annotations,
  entities,
  newShape,
  selectedTool,
} from "$lib/stores/workspaceStores.svelte";
import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
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
  annotations.update((objects) =>
    objects.map((ann) => {
      if (selectedTool.value.type === ToolType.Pan || selectedTool.value.type === ToolType.Fusion) {
        ann.ui.displayControl = {
          ...ann.ui.displayControl,
          highlighted: isHighlighted ? "all" : getTopEntity(ann).id === entity_id ? "self" : "none",
        };
      }
      if (getTopEntity(ann).id === entity_id && ann.is_type(BaseSchema.Tracklet)) {
        trackStart = Math.min(trackStart, (ann as Tracklet).data.start_timestep);
        trackEnd = Math.max(trackEnd, (ann as Tracklet).data.end_timestep);
      }
      return ann;
    }),
  );
  // Auto-expand the entity card and scroll it into view
  if (!isHighlighted) {
    entities.update((ents) => {
      let hasChanged = false;
      const nextEntities = ents.map((ent) => {
        if (ent.id === entity_id) {
          if (!ent.ui.displayControl.open) {
            hasChanged = true;
            ent.ui.displayControl = { ...ent.ui.displayControl, open: true };
          }
        } else if (ent.ui.displayControl.open) {
          hasChanged = true;
          ent.ui.displayControl = { ...ent.ui.displayControl, open: false };
        }
        return ent;
      });
      return hasChanged ? nextEntities : ents;
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
