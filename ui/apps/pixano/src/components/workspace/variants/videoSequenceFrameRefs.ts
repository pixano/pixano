/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference } from "$lib/types/dataset";

type SequenceFrameLike = {
  id: string;
  data: {
    frame_index: number | string;
  };
};

export function buildCurrentSequenceFrameRefsByView(
  views: Record<string, SequenceFrameLike[]>,
  frameIndex: number,
): Record<string, Reference> {
  const refs: Record<string, Reference> = {};

  for (const [viewName, frames] of Object.entries(views)) {
    const frame = frames.find((candidate) => Number(candidate.data.frame_index) === frameIndex);
    if (!frame) continue;
    refs[viewName] = { id: frame.id, name: viewName };
  }

  return refs;
}
