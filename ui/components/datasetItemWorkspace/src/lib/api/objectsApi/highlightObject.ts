/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Entity, Tracklet, BaseSchema } from "@pixano/core";
import { annotations } from "../../stores/datasetItemWorkspaceStores";
import { getTopEntity } from "./getTopEntity";

export const highlightObject = (
  entity: Entity,
  entities: Entity[],
  isHighlighted: boolean,
  currentFrameIndex: number,
  lastFrameIndex: number,
): number => {
  let objectAlreadyVisible = false;
  let highlightFrameIndex = lastFrameIndex + 1;
  annotations.update((objects) =>
    objects.map((ann) => {
      ann.ui.highlighted = isHighlighted
        ? "all"
        : getTopEntity(ann, entities).id === entity.id
          ? "self"
          : "none";
      if (
        !objectAlreadyVisible &&
        getTopEntity(ann, entities).id === entity.id &&
        ann.is_type(BaseSchema.Tracklet) &&
        ann.ui.highlighted === "self" &&
        (ann as Tracklet).data.start_timestep < highlightFrameIndex
      ) {
        if (
          currentFrameIndex >= (ann as Tracklet).data.start_timestep &&
          currentFrameIndex <= (ann as Tracklet).data.end_timestep
        ) {
          objectAlreadyVisible = true;
        } else {
          highlightFrameIndex = (ann as Tracklet).data.start_timestep;
        }
      }
      return ann;
    }),
  );
  const cardElement = document.querySelector(`#card-object-${entity.id}`);
  if (cardElement) {
    cardElement.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  const trackElement = document.querySelector(`#video-object-${entity.id}`);
  if (trackElement) {
    trackElement.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  if (!objectAlreadyVisible && highlightFrameIndex != lastFrameIndex + 1) {
    return highlightFrameIndex;
  } else {
    return currentFrameIndex;
  }
};
