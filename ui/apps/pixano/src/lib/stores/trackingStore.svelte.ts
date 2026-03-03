/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MultiSegmentTracker, type BBoxKeyframe } from "$lib/trackers";
import { BBox, BaseSchema, WorkspaceType, type Reference, type SequenceFrame } from "$lib/types/dataset";
import { ShapeType, type SaveRectangleShape } from "$lib/types/shapeTypes";
import { reactiveStore, reactiveDerived } from "./reactiveStore.svelte";
import { currentFrameIndex } from "./videoStores.svelte";
import { views } from "./workspaceStores.svelte";

// ─── Session state ──────────────────────────────────────────────────────────

export interface TrackingSessionState {
  tracker: MultiSegmentTracker | null;
  version: number;
  viewRef: Reference | null;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
  pendingKeyframe: { frameIndex: number; coords: readonly [number, number, number, number] } | null;
}

const NULL_STATE: TrackingSessionState = {
  tracker: null,
  version: 0,
  viewRef: null,
  itemId: "",
  imageWidth: 0,
  imageHeight: 0,
  pendingKeyframe: null,
};

export const trackingSession = reactiveStore<TrackingSessionState>({ ...NULL_STATE });

// ─── Actions ────────────────────────────────────────────────────────────────

export function startTrackingSession(
  viewName: string,
  viewRef: Reference,
  itemId: string,
  imageWidth: number,
  imageHeight: number,
): void {
  const tracker = new MultiSegmentTracker(viewName);
  trackingSession.value = {
    tracker,
    version: tracker.version,
    viewRef,
    itemId,
    imageWidth,
    imageHeight,
    pendingKeyframe: null,
  };
}

export function addTrackingKeyframe(
  frameIndex: number,
  coords: readonly [number, number, number, number],
): void {
  const { tracker } = trackingSession.value;
  if (!tracker) return;
  tracker.addKeyframe({ frameIndex, coords });
  trackingSession.update((s) => ({ ...s, version: tracker.version }));
}

export function promoteCurrentFrame(
  coords?: readonly [number, number, number, number],
): void {
  const { tracker } = trackingSession.value;
  if (!tracker) return;
  const frameIndex = currentFrameIndex.value;
  if (coords) {
    tracker.addKeyframe({ frameIndex, coords });
  } else {
    tracker.promoteToKeyframe(frameIndex);
  }
  trackingSession.update((s) => ({ ...s, version: tracker.version }));
}

export function setPendingKeyframe(
  frameIndex: number,
  coords: readonly [number, number, number, number],
): void {
  const { tracker } = trackingSession.value;
  if (!tracker) return;
  trackingSession.update((s) => ({ ...s, pendingKeyframe: { frameIndex, coords } }));
}

export function confirmPendingKeyframe(): boolean {
  const { tracker, pendingKeyframe } = trackingSession.value;
  if (!tracker) return false;

  if (pendingKeyframe) {
    tracker.addKeyframe({ frameIndex: pendingKeyframe.frameIndex, coords: pendingKeyframe.coords });
    trackingSession.update((s) => ({ ...s, version: tracker.version, pendingKeyframe: null }));
    return true;
  }

  // No pending — try promoting current interpolated frame to keyframe
  const frameIndex = currentFrameIndex.value;
  const result = tracker.interpolateAt(frameIndex);
  if (result && !result.isKeyframe) {
    tracker.promoteToKeyframe(frameIndex);
    trackingSession.update((s) => ({ ...s, version: tracker.version }));
    return true;
  }

  return false;
}

export function discardPendingKeyframe(): void {
  trackingSession.update((s) => ({ ...s, pendingKeyframe: null }));
}

export function startNewTrackingSegment(): boolean {
  const { tracker } = trackingSession.value;
  if (!tracker) return false;
  const started = tracker.startNewSegment();
  if (started) {
    trackingSession.update((s) => ({ ...s, version: tracker.version, pendingKeyframe: null }));
  }
  return started;
}

export function cancelTrackingSession(): void {
  const { tracker } = trackingSession.value;
  if (tracker) tracker.clear();
  trackingSession.value = { ...NULL_STATE };
}

export function finalizeTrackingSession(): SaveRectangleShape | null {
  const { tracker, viewRef, itemId, imageWidth, imageHeight } = trackingSession.value;
  if (!tracker || !viewRef || tracker.keyframeCount === 0) return null;

  // Use current frame's coords so the save shape appears where the user is looking
  const frameIdx = currentFrameIndex.value;
  const result = tracker.interpolateAt(frameIdx);
  const coords = result ? result.data.coords : tracker.sortedKeyframes[0].coords;

  return {
    status: "saving",
    type: ShapeType.bbox,
    viewRef,
    itemId,
    imageWidth,
    imageHeight,
    attrs: {
      x: coords[0] * imageWidth,
      y: coords[1] * imageHeight,
      width: coords[2] * imageWidth,
      height: coords[3] * imageHeight,
    },
  };
}

// ─── Derived stores ─────────────────────────────────────────────────────────

export const isTracking = reactiveDerived(() => trackingSession.value.tracker !== null);

export const trackingPreviewBBoxes = reactiveDerived<BBox[]>(() => {
  const { tracker, version, imageWidth, imageHeight, pendingKeyframe } = trackingSession.value;
  if (!tracker || version < 0) return []; // version read for reactivity

  const frameIdx = currentFrameIndex.value;

  // Pending edit on this frame → show pending coords, keep editable
  if (pendingKeyframe && pendingKeyframe.frameIndex === frameIdx) {
    const bbox = buildTrackingPreviewBBox(
      { frameIndex: frameIdx, coords: pendingKeyframe.coords },
      false,
      tracker.viewName,
      imageWidth,
      imageHeight,
      true,
    );
    if (bbox?.ui) {
      bbox.ui.opacity = 0.85;
      bbox.ui.strokeFactor = 1.5;
      bbox.ui.tooltip = "Edited — press T to confirm";
    }
    return bbox ? [bbox] : [];
  }

  const result = tracker.interpolateAt(frameIdx);
  if (!result) return [];

  const editable = !result.isKeyframe; // interpolated → editable
  const bbox = buildTrackingPreviewBBox(
    result.data,
    result.isKeyframe,
    tracker.viewName,
    imageWidth,
    imageHeight,
    editable,
  );
  return bbox ? [bbox] : [];
});

export const trackingKeyframeIndices = reactiveDerived<number[]>(() => {
  const { tracker, version } = trackingSession.value;
  if (!tracker || version < 0) return [];
  return tracker.sortedKeyframes.map((kf) => kf.frameIndex);
});

export const trackingFrameRange = reactiveDerived<[number, number] | null>(() => {
  const { tracker, version } = trackingSession.value;
  if (!tracker || version < 0) return null;
  const start = tracker.startFrame;
  const end = tracker.endFrame;
  if (start === undefined || end === undefined) return null;
  return [start, end];
});

export const trackingSegmentRanges = reactiveDerived<Array<[number, number]>>(() => {
  const { tracker, version } = trackingSession.value;
  if (!tracker || version < 0) return [];
  return tracker.segmentRanges;
});

export const isAwaitingNewSegmentKeyframe = reactiveDerived<boolean>(() => {
  const { tracker, version } = trackingSession.value;
  if (!tracker || version < 0) return false;
  return tracker.segmentCount > 1 && tracker.activeSegment.keyframeCount === 0;
});

export const hasPendingKeyframe = reactiveDerived(() => trackingSession.value.pendingKeyframe !== null);

export const pendingKeyframeIndex = reactiveDerived<number | null>(() => {
  return trackingSession.value.pendingKeyframe?.frameIndex ?? null;
});

// ─── Helpers ────────────────────────────────────────────────────────────────

function buildTrackingPreviewBBox(
  kf: BBoxKeyframe,
  isKeyframe: boolean,
  viewName: string,
  imageWidth: number,
  imageHeight: number,
  editable = false,
): BBox | null {
  const viewFrames = views.value[viewName];
  if (!Array.isArray(viewFrames)) return null;
  const frame = viewFrames[kf.frameIndex] as SequenceFrame | undefined;
  if (!frame) return null;

  const pixelCoords = [
    kf.coords[0] * imageWidth,
    kf.coords[1] * imageHeight,
    kf.coords[2] * imageWidth,
    kf.coords[3] * imageHeight,
  ];

  const syntheticId = `tracking-preview-${kf.frameIndex}`;
  const bbox = new BBox({
    id: syntheticId,
    table_info: { name: "_tracking_preview", group: "annotations", base_schema: BaseSchema.BBox },
    created_at: "",
    updated_at: "",
    data: {
      coords: pixelCoords,
      format: "xywh",
      is_normalized: false,
      confidence: 1.0,
      item_id: "",
      view_name: viewName,
      frame_id: frame.id,
      entity_id: "",
      source_id: "",
    },
  });

  bbox.ui = {
    datasetItemType: WorkspaceType.VIDEO,
    displayControl: { hidden: false, editing: editable, highlighted: "self" },
    frame_index: kf.frameIndex,
    opacity: isKeyframe ? 1.0 : 0.7,
    strokeFactor: isKeyframe ? 2.0 : 1.0,
    tooltip: isKeyframe ? "Keyframe" : "Interpolated",
  };

  return bbox;
}
