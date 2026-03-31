/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference, SequenceFrame } from "$lib/types/dataset";

export interface ViewLocator {
  id: string;
  logicalName: string;
}

export interface FrameLocator {
  frameId: string;
  logicalName: string;
  frameIndex: number;
}

export type WorkspaceLocator = ViewLocator | FrameLocator;

export function isFrameLocator(locator: WorkspaceLocator): locator is FrameLocator {
  return "frameId" in locator;
}

export function getLocatorLogicalName(locator: WorkspaceLocator): string {
  return locator.logicalName;
}

export function getLocatorId(locator: WorkspaceLocator): string {
  return isFrameLocator(locator) ? locator.frameId : locator.id;
}

export function toViewLocator(reference: Reference): ViewLocator {
  return {
    id: reference.id,
    logicalName: reference.name,
  };
}

export function toFrameLocator(reference: Reference, frameIndex: number): FrameLocator {
  return {
    frameId: reference.id,
    logicalName: reference.name,
    frameIndex,
  };
}

export function toLegacyReference(locator: WorkspaceLocator): Reference {
  return {
    id: getLocatorId(locator),
    name: getLocatorLogicalName(locator),
  };
}

export function buildFrameLocator(frame: SequenceFrame, logicalName: string): FrameLocator {
  return {
    frameId: frame.id,
    logicalName,
    frameIndex: frame.data.frame_index,
  };
}
