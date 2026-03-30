/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference, SequenceFrame } from "$lib/types/dataset";

export function resolveSequenceFrameRef(
  viewName: string,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
  fallback: Reference,
): Reference {
  if (!viewFrames || !Number.isFinite(frameIndex) || frameIndex < 0) {
    return fallback;
  }

  const frame =
    viewFrames.find((candidate) => candidate.data.frame_index === frameIndex) ?? viewFrames[frameIndex];
  if (!frame) {
    return fallback;
  }

  return { id: frame.id, name: viewName };
}

export function resolveVideoFrameIdentity(
  viewRef: Reference,
  frameIndex: number,
  viewFrames: SequenceFrame[] | undefined,
): { viewRef: Reference; frameIndex: number } {
  return {
    viewRef: resolveSequenceFrameRef(viewRef.name, frameIndex, viewFrames, viewRef),
    frameIndex,
  };
}
