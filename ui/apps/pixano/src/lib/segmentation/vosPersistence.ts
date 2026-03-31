/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";
import { nanoid } from "nanoid";

import {
  cloneMaskUiForPersistence,
  cloneTrackingMaskOutput,
  normalizeTrackingMaskOutputForPersistence,
  type TrackingMaskSourceInput,
} from "$lib/segmentation/maskNormalization";
import { Mask } from "$lib/types/dataset";

export interface PersistedVosMaskSessionEntry {
  frameIndex: number;
  segmentId: number;
  output: MaskSegmentationOutput;
}

export interface BuildPersistedVosMasksInput {
  sessionMasks: PersistedVosMaskSessionEntry[];
  currentFrameIndex: number;
  entityId: string;
  tableInfo: Mask["table_info"];
  uiTemplate: Mask["ui"];
  fallbackSource?: TrackingMaskSourceInput;
}

export interface BuildPersistedVosMasksResult {
  currentMask: Mask | null;
  trackingMasks: Mask[];
  allMasks: Mask[];
  masksBySegment: Map<number, Mask[]>;
  lastFrameIndex: number;
}

export function buildPersistedVosMasks(
  input: BuildPersistedVosMasksInput,
): BuildPersistedVosMasksResult {
  const sortedSessionMasks = input.sessionMasks
    .slice()
    .sort((left, right) => left.frameIndex - right.frameIndex);

  const trackingMasks: Mask[] = [];
  const allMasks: Mask[] = [];
  const masksBySegment = new Map<number, Mask[]>();
  let currentMask: Mask | null = null;
  let lastFrameIndex = input.currentFrameIndex;

  for (const sessionMask of sortedSessionMasks) {
    const normalizedOutput = normalizeTrackingMaskOutputForPersistence(
      cloneTrackingMaskOutput(sessionMask.output),
      input.fallbackSource,
    );
    const persistedOutput = {
      ...normalizedOutput,
      id: nanoid(10),
      table_info: { ...input.tableInfo },
    };
    const annotation = new Mask(persistedOutput);
    const frameIndex = persistedOutput.data.frame_index;

    annotation.table_info = { ...input.tableInfo };
    annotation.data.entity_id = input.entityId;
    annotation.data.view_name = persistedOutput.data.view_name;
    annotation.data.frame_id = persistedOutput.data.frame_id;
    annotation.data.frame_index = frameIndex;
    annotation.ui = cloneMaskUiForPersistence(input.uiTemplate, frameIndex);

    allMasks.push(annotation);
    const segmentAnnotations = masksBySegment.get(sessionMask.segmentId) ?? [];
    segmentAnnotations.push(annotation);
    masksBySegment.set(sessionMask.segmentId, segmentAnnotations);
    lastFrameIndex = Math.max(lastFrameIndex, frameIndex);

    if (frameIndex === input.currentFrameIndex) {
      currentMask = annotation;
      continue;
    }

    trackingMasks.push(annotation);
  }

  return {
    currentMask,
    trackingMasks,
    allMasks,
    masksBySegment,
    lastFrameIndex,
  };
}
