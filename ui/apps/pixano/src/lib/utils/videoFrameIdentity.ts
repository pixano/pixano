/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SequenceFrame } from "$lib/types/dataset";
import {
  buildFrameLocator,
  isFrameLocator,
  type FrameLocator,
  type ViewLocator,
  type WorkspaceLocator,
} from "$lib/types/workspaceLocators";

export function resolveSequenceFrameLocator(
  logicalName: string,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
  fallback: WorkspaceLocator,
): FrameLocator {
  if (!viewFrames || !Number.isFinite(frameIndex) || frameIndex < 0) {
    return isFrameLocator(fallback)
      ? fallback
      : {
          frameId: fallback.id,
          logicalName: fallback.logicalName,
          frameIndex,
        };
  }

  const frame =
    viewFrames.find((candidate) => candidate.data.frame_index === frameIndex) ?? viewFrames[frameIndex];
  if (!frame) {
    return isFrameLocator(fallback)
      ? fallback
      : {
          frameId: fallback.id,
          logicalName: fallback.logicalName,
          frameIndex,
        };
  }

  return buildFrameLocator(frame, logicalName);
}

export function resolveVideoFrameIdentity(
  viewLocator: ViewLocator | FrameLocator,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
): { frameLocator: FrameLocator; frameIndex: number } {
  return {
    frameLocator: resolveSequenceFrameLocator(
      viewLocator.logicalName,
      frameIndex,
      viewFrames,
      viewLocator,
    ),
    frameIndex,
  };
}
