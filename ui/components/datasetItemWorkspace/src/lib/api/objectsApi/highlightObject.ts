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
  let trackStart = get(lastFrameIndex) + 1;
  let trackEnd = 0;
  annotations.update((objects) =>
    objects.map((ann) => {
      if (get(selectedTool).type === ToolType.Pan) {
        ann.ui.displayControl.highlighted = isHighlighted
          ? "all"
          : getTopEntity(ann).id === entity_id
            ? "self"
            : "none";
      }
      if (getTopEntity(ann).id === entity_id && ann.is_type(BaseSchema.Tracklet)) {
        trackStart = Math.min(trackStart, (ann as Tracklet).data.start_timestep);
        trackEnd = Math.max(trackEnd, (ann as Tracklet).data.end_timestep);
      }
      return ann;
    }),
  );
  // Scroll
  if (!isHighlighted) scrollIntoView(entity_id);
  // Return frame index
  if (
    !isHighlighted &&
    (get(currentFrameIndex) < trackStart || get(currentFrameIndex) > trackEnd)
  ) {
    return trackStart;
  } else {
    return get(currentFrameIndex);
  }
};
