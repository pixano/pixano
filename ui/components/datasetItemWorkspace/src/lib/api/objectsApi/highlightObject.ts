/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Entity, Tracklet, BaseSchema } from "@pixano/core";
import { annotations } from "../../stores/datasetItemWorkspaceStores";
import { currentFrameIndex } from "../../stores/videoViewerStores";
import { getTopEntity } from "./getTopEntity";

export const highlightObject = (
  entity: Entity,
  entities: Entity[],
  isHighlighted: boolean,
  lastFrameIndex: number,
) => {
  let highlightFrameIndex = lastFrameIndex + 1;
  console.log(entity.id, isHighlighted);
  annotations.update((objects) =>
    objects.map((ann) => {
      ann.ui.highlighted = isHighlighted
        ? "all"
        : getTopEntity(ann, entities).id === entity.id
          ? "self"
          : "none";
      if (
        getTopEntity(ann, entities).id === entity.id &&
        ann.is_type(BaseSchema.Tracklet) &&
        ann.ui.highlighted === "self" &&
        (ann as Tracklet).data.start_timestep < highlightFrameIndex
      ) {
        highlightFrameIndex = (ann as Tracklet).data.start_timestep;
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
  if (highlightFrameIndex != lastFrameIndex + 1) {
    currentFrameIndex.set(highlightFrameIndex);
  }
};
