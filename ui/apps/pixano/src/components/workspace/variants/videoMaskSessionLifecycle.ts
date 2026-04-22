/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType } from "$lib/tools";
import { ShapeType, type Shape } from "$lib/types/shapeTypes";

type VideoMaskSessionState = {
  isVosSessionActive: boolean;
  hasTracker: boolean;
  hasActiveJob: boolean;
};

export type VideoMaskResetAction = "ignore" | "clear-preview" | "reset-smart-tracking";

function hasLiveVideoMaskSession(state: VideoMaskSessionState): boolean {
  return state.isVosSessionActive || state.hasTracker || state.hasActiveJob;
}

export function resolveVideoMaskResetAction(
  shape: Shape,
  state: VideoMaskSessionState,
): VideoMaskResetAction {
  if (shape.status !== "none" || !shape.shouldReset) return "ignore";
  if (shape.resetReason !== "save-confirmed" || shape.resetShapeType !== ShapeType.mask) {
    return "ignore";
  }
  return hasLiveVideoMaskSession(state) ? "reset-smart-tracking" : "clear-preview";
}

export function shouldClearVideoMaskSessionOnToolSwitch(
  toolType: ToolType | undefined,
  state: VideoMaskSessionState,
): boolean {
  return toolType !== ToolType.VOS && hasLiveVideoMaskSession(state);
}

export function shouldHydrateVideoPreview(
  toolType: ToolType | undefined,
  state: VideoMaskSessionState,
): boolean {
  return toolType === ToolType.VOS && hasLiveVideoMaskSession(state);
}
