/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { BaseSchema, Entity, Tracklet } from "@pixano/core";

import { annotations } from "../../stores/datasetItemWorkspaceStores";
import { currentFrameIndex, lastFrameIndex } from "../../stores/videoViewerStores";
import { getTopEntity } from "./getTopEntity";

export const highlightObject = (entity: Entity, isHighlighted: boolean): number => {
  let highlightFrameIndex = get(lastFrameIndex) + 1;
  annotations.update((objects) =>
    objects.map((ann) => {
      ann.ui.highlighted = isHighlighted
        ? "all"
        : getTopEntity(ann).id === entity.id
          ? "self"
          : "none";
      if (getTopEntity(ann).id === entity.id && ann.is_type(BaseSchema.Tracklet)) {
        highlightFrameIndex = Math.min(highlightFrameIndex, (ann as Tracklet).data.start_timestep);
      }
      return ann;
    }),
  );
  const cardElement = document.querySelector(`#card-object-${entity.id}`);
  if (cardElement) {
    cardElement.scrollIntoView({ block: "center" });
  }
  const trackElement = document.querySelector(`#video-object-${entity.id}`);
  if (trackElement) {
    trackElement.scrollIntoView({ block: "center" });
  }
  if (highlightFrameIndex != get(lastFrameIndex) + 1) {
    return highlightFrameIndex;
  } else {
    return get(currentFrameIndex);
  }
};
