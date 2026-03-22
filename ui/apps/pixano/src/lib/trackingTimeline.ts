/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type TrackingTimelineVariant = "bbox" | "vos";

export interface TrackingTimelineState {
  variant: TrackingTimelineVariant;
  segments: Array<[number, number]>;
  keyframes: number[];
  pendingMarkerIndex: number | null;
  pendingInterval: [number, number] | null;
}

export interface TrackingTimelineBarVisual {
  startFrame: number;
  endFrame: number;
  label: string | null;
}

export interface TrackingTimelineMarkerVisual {
  frameIndex: number;
  kind: "keyframe" | "pending";
}

export interface TrackingTimelineVisualState {
  completedBars: TrackingTimelineBarVisual[];
  pendingBar: TrackingTimelineBarVisual | null;
  markers: TrackingTimelineMarkerVisual[];
}

function uniqueSortedFrameIndices(frameIndices: number[]): number[] {
  return [...new Set(frameIndices)].sort((left, right) => left - right);
}

function normalizeSegments(segments: Array<[number, number]>): Array<[number, number]> {
  return segments
    .map(
      ([startFrame, endFrame]) =>
        (startFrame <= endFrame ? [startFrame, endFrame] : [endFrame, startFrame]) as [
          number,
          number,
        ],
    )
    .sort((left, right) => left[0] - right[0]);
}

function getSingleSegmentLabel(state: TrackingTimelineState): string {
  if (state.variant === "vos" && state.keyframes.length <= 1) {
    return "1 anchor — scrub forward and press T";
  }
  if (state.keyframes.length <= 1) {
    return "1 keyframe — navigate to another frame and draw";
  }
  return "Tracking...";
}

export function buildTrackingTimelineVisualState(
  state: TrackingTimelineState,
): TrackingTimelineVisualState {
  const segments = normalizeSegments(state.segments);
  const keyframes = uniqueSortedFrameIndices(state.keyframes);
  const hasMultipleSegments = segments.length > 1;
  const hasPendingInterval = state.pendingInterval !== null;

  const completedBars = segments.map(([startFrame, endFrame], segmentIndex) => ({
    startFrame,
    endFrame,
    label: hasMultipleSegments
      ? `Seg ${segmentIndex + 1}`
      : hasPendingInterval
        ? null
        : getSingleSegmentLabel({ ...state, keyframes }),
  }));

  const pendingBar =
    state.pendingInterval === null
      ? null
      : {
          startFrame: Math.min(state.pendingInterval[0], state.pendingInterval[1]),
          endFrame: Math.max(state.pendingInterval[0], state.pendingInterval[1]),
          label: "Tracking...",
        };

  const markers: TrackingTimelineMarkerVisual[] = keyframes.map((frameIndex) => ({
    frameIndex,
    kind: "keyframe",
  }));
  if (state.pendingMarkerIndex !== null) {
    markers.push({ frameIndex: state.pendingMarkerIndex, kind: "pending" });
  }

  return {
    completedBars,
    pendingBar,
    markers,
  };
}
