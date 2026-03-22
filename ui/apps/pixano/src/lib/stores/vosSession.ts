/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";
import {
  cloneTrackingMaskOutput,
  saveMaskShapeToTrackingOutput,
} from "$lib/segmentation/maskNormalization";
import type { Reference } from "$lib/types/dataset";
import type { InteractiveSegmenterAIInput } from "$lib/types/tools";
import type { SaveMaskShape } from "$lib/types/shapeTypes";

export type VosAnchorSourceKind = "prompt" | "mask";

export interface VosAnchorState {
  frameIndex: number;
  viewRef: Reference;
  sourceKind: VosAnchorSourceKind;
  prompt: InteractiveSegmenterAIInput["prompt"] | null;
  mask: SaveMaskShape;
}

export interface VosSegmentState {
  id: number;
  viewName: string;
  startFrame: number;
  endFrame: number;
}

export interface VosTrackedMaskState {
  frameIndex: number;
  segmentId: number;
  output: MaskSegmentationOutput;
}

export interface VosPendingIntervalState {
  requestId: string;
  startFrame: number;
  endFrame: number;
  direction: "forward" | "backward";
}

export interface VosSessionState {
  viewName: string | null;
  anchor: VosAnchorState | null;
  segments: VosSegmentState[];
  activeSegmentId: number | null;
  masks: VosTrackedMaskState[];
  pendingInterval: VosPendingIntervalState | null;
  nextSegmentId: number;
}

export const NULL_VOS_STATE: VosSessionState = {
  viewName: null,
  anchor: null,
  segments: [],
  activeSegmentId: null,
  masks: [],
  pendingInterval: null,
  nextSegmentId: 1,
};

function cloneVosPrompt(
  prompt: InteractiveSegmenterAIInput["prompt"] | null,
): InteractiveSegmenterAIInput["prompt"] | null {
  if (!prompt) return null;
  return {
    points: prompt.points.map((point) => ({ ...point })),
    box: prompt.box ? { ...prompt.box } : null,
  };
}

function upsertVosMask(
  masks: VosTrackedMaskState[],
  nextMask: VosTrackedMaskState,
): VosTrackedMaskState[] {
  const existingIndex = masks.findIndex((mask) => mask.frameIndex === nextMask.frameIndex);
  if (existingIndex === -1) {
    return [...masks, nextMask].sort((left, right) => left.frameIndex - right.frameIndex);
  }

  const next = [...masks];
  next[existingIndex] = nextMask;
  next.sort((left, right) => left.frameIndex - right.frameIndex);
  return next;
}

function upsertVosSegment(
  segments: VosSegmentState[],
  nextSegment: VosSegmentState,
): VosSegmentState[] {
  const existingIndex = segments.findIndex((segment) => segment.id === nextSegment.id);
  if (existingIndex === -1) {
    return [...segments, nextSegment].sort((left, right) => left.startFrame - right.startFrame);
  }

  const next = [...segments];
  next[existingIndex] = nextSegment;
  next.sort((left, right) => left.startFrame - right.startFrame);
  return next;
}

function ensureActiveVosSegment(
  state: VosSessionState,
  viewName: string,
  frameIndex: number,
): VosSessionState {
  if (state.activeSegmentId !== null) {
    const activeSegment = state.segments.find((segment) => segment.id === state.activeSegmentId);
    if (activeSegment && activeSegment.viewName === viewName) {
      const widenedSegment = {
        ...activeSegment,
        startFrame: Math.min(activeSegment.startFrame, frameIndex),
        endFrame: Math.max(activeSegment.endFrame, frameIndex),
      };
      return {
        ...state,
        segments: upsertVosSegment(state.segments, widenedSegment),
      };
    }
  }

  const nextSegment: VosSegmentState = {
    id: state.nextSegmentId,
    viewName,
    startFrame: frameIndex,
    endFrame: frameIndex,
  };
  return {
    ...state,
    viewName,
    activeSegmentId: nextSegment.id,
    nextSegmentId: state.nextSegmentId + 1,
    segments: upsertVosSegment(state.segments, nextSegment),
  };
}

export function setVosAnchorState(
  currentState: VosSessionState,
  input: {
    frameIndex: number;
    viewRef: Reference;
    sourceKind: VosAnchorSourceKind;
    prompt: InteractiveSegmenterAIInput["prompt"] | null;
    mask: SaveMaskShape;
    output?: MaskSegmentationOutput;
  },
): VosSessionState {
  let nextState = currentState;
  if (currentState.viewName && currentState.viewName !== input.viewRef.name) {
    nextState = { ...NULL_VOS_STATE };
  }

  nextState = ensureActiveVosSegment(nextState, input.viewRef.name, input.frameIndex);
  if (nextState.activeSegmentId === null) {
    return nextState;
  }

  const output = cloneTrackingMaskOutput(
    input.output ?? saveMaskShapeToTrackingOutput(input.mask, input.frameIndex),
  );
  return {
    ...nextState,
    anchor: {
      frameIndex: input.frameIndex,
      viewRef: input.viewRef,
      sourceKind: input.sourceKind,
      prompt: cloneVosPrompt(input.prompt),
      mask: input.mask,
    },
    masks: upsertVosMask(nextState.masks, {
      frameIndex: input.frameIndex,
      segmentId: nextState.activeSegmentId,
      output,
    }),
  };
}

export function beginVosPendingIntervalState(
  state: VosSessionState,
  input: VosPendingIntervalState,
): VosSessionState {
  return {
    ...state,
    pendingInterval: {
      requestId: input.requestId,
      startFrame: input.startFrame,
      endFrame: input.endFrame,
      direction: input.direction,
    },
  };
}

export function commitVosIntervalState(
  state: VosSessionState,
  input: {
    requestId: string;
    outputs: MaskSegmentationOutput[];
    nextAnchor: VosAnchorState;
  },
): VosSessionState {
  if (state.pendingInterval?.requestId !== input.requestId) {
    return state;
  }

  const nextState = ensureActiveVosSegment(state, input.nextAnchor.viewRef.name, input.nextAnchor.frameIndex);
  if (nextState.activeSegmentId === null) {
    return {
      ...nextState,
      pendingInterval: null,
    };
  }

  let nextMasks = nextState.masks;
  let segmentEnd = input.nextAnchor.frameIndex;
  for (const output of input.outputs) {
    const frameIndex = output.data.frame_index;
    segmentEnd = Math.max(segmentEnd, frameIndex);
    nextMasks = upsertVosMask(nextMasks, {
      frameIndex,
      segmentId: nextState.activeSegmentId,
      output: cloneTrackingMaskOutput(output),
    });
  }

  const activeSegment = nextState.segments.find((segment) => segment.id === nextState.activeSegmentId);
  const widenedSegment =
    activeSegment === undefined
      ? undefined
      : {
          ...activeSegment,
          startFrame: Math.min(activeSegment.startFrame, input.nextAnchor.frameIndex),
          endFrame: Math.max(activeSegment.endFrame, segmentEnd),
        };

  return {
    ...nextState,
    anchor: {
      frameIndex: input.nextAnchor.frameIndex,
      viewRef: input.nextAnchor.viewRef,
      sourceKind: input.nextAnchor.sourceKind,
      prompt: cloneVosPrompt(input.nextAnchor.prompt),
      mask: input.nextAnchor.mask,
    },
    pendingInterval: null,
    masks: nextMasks,
    segments: widenedSegment
      ? upsertVosSegment(nextState.segments, widenedSegment)
      : nextState.segments,
  };
}

export function failVosPendingIntervalState(
  state: VosSessionState,
  requestId: string,
): VosSessionState {
  if (state.pendingInterval?.requestId !== requestId) {
    return state;
  }
  return {
    ...state,
    pendingInterval: null,
  };
}

export function startNewVosSegmentState(state: VosSessionState): VosSessionState {
  if (
    state.anchor === null &&
    state.activeSegmentId === null &&
    state.pendingInterval === null &&
    state.masks.length === 0
  ) {
    return state;
  }

  return {
    ...state,
    anchor: null,
    activeSegmentId: null,
    pendingInterval: null,
  };
}

export function isVosSessionActiveState(state: VosSessionState): boolean {
  return (
    state.anchor !== null ||
    state.pendingInterval !== null ||
    state.masks.length > 0 ||
    state.segments.length > 0
  );
}
