/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import type { Reference, SequenceFrame } from "@pixano/core";

import { views } from "../../stores/datasetItemWorkspaceStores";

export const getFrameIndexFromViewRef = (viewRef: Reference): number => {
  const vs = get(views);
  if (!Array.isArray(vs[viewRef.name])) return 0;
  const view = (vs[viewRef.name] as SequenceFrame[]).find((sf) => sf.id === viewRef.id);
  if (view) return view.data.frame_index;
  else {
    console.error("Could not find a matching view:", viewRef);
    return 0;
  }
};
