/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type TrackingTimelineVariant = "bbox" | "vos" | "detection";

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
          label: state.variant === "detection" ? "Detecting and tracking..." : "Tracking...",
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

// ─── Tracking by detection: one lane per proposed track ─────────────────────

export type DetectionTimelineLaneState = "kept" | "discarded" | "selected";

export interface DetectionTimelineLane {
  trackId: number;
  label: string;
  color: string;
  segments: Array<[number, number]>;
  state: DetectionTimelineLaneState;
}

export interface DetectionTimelineTrackInput {
  trackId: number;
  className: string | null;
  frames: Array<{ frameIndex: number }>;
}

export function buildDetectionTimelineLanes(
  tracks: DetectionTimelineTrackInput[],
  options: {
    discardedTrackIds: Iterable<number>;
    selectedTrackId: number | null;
    maxGapFrames: number;
    colorOf: (trackId: number) => string;
  },
): DetectionTimelineLane[] {
  const discarded = new Set(options.discardedTrackIds);
  return tracks.map((track) => {
    const segments: Array<[number, number]> = [];
    for (const frame of track.frames) {
      const last = segments[segments.length - 1];
      if (last && frame.frameIndex - last[1] <= options.maxGapFrames) {
        last[1] = frame.frameIndex;
      } else {
        segments.push([frame.frameIndex, frame.frameIndex]);
      }
    }
    return {
      trackId: track.trackId,
      label: `${track.className ?? "object"} #${track.trackId}`,
      color: options.colorOf(track.trackId),
      segments,
      state:
        options.selectedTrackId === track.trackId
          ? "selected"
          : discarded.has(track.trackId)
            ? "discarded"
            : "kept",
    };
  });
}
