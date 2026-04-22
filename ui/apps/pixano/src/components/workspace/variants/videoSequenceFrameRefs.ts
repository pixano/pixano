/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { FrameLocator } from "$lib/types/workspaceLocators";

type SequenceFrameLike = {
  id: string;
  data: {
    frame_index: number | string;
  };
};

export function buildCurrentSequenceFrameLocatorsByView(
  views: Record<string, SequenceFrameLike[]>,
  frameIndex: number,
): Record<string, FrameLocator> {
  const locators: Record<string, FrameLocator> = {};

  for (const [logicalName, frames] of Object.entries(views)) {
    const frame = frames.find((candidate) => Number(candidate.data.frame_index) === frameIndex);
    if (!frame) continue;
    locators[logicalName] = {
      frameId: frame.id,
      logicalName,
      frameIndex,
    };
  }

  return locators;
}
