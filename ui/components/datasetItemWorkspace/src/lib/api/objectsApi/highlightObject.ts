/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import { ToolType } from "@pixano/canvas2d/src/tools";
import { BaseSchema, Tracklet } from "@pixano/core";

import { annotations, selectedTool } from "../../stores/datasetItemWorkspaceStores";
import { currentFrameIndex, lastFrameIndex } from "../../stores/videoViewerStores";
import { getTopEntity } from "./getTopEntity";
import { scrollIntoView } from "./scrollIntoView";

export const highlightObject = (entity_id: string, isHighlighted: boolean): number => {
  let highlightFrameIndex = get(lastFrameIndex) + 1;
  annotations.update((objects) =>
    objects.map((ann) => {
      if (get(selectedTool).type === ToolType.Pan) {
        ann.ui.highlighted = isHighlighted
          ? "all"
          : getTopEntity(ann).id === entity_id
            ? "self"
            : "none";
      }
      if (getTopEntity(ann).id === entity_id && ann.is_type(BaseSchema.Tracklet)) {
        highlightFrameIndex = Math.min(highlightFrameIndex, (ann as Tracklet).data.start_timestep);
      }
      return ann;
    }),
  );
  if (!isHighlighted) scrollIntoView(entity_id);
  if (!isHighlighted && highlightFrameIndex != get(lastFrameIndex) + 1) {
    return highlightFrameIndex;
  } else {
    return get(currentFrameIndex);
  }
};
