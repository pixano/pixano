/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Tracking by detection: a prompt-free tracking model (YOLO + ByteTrack) follows what it detects
 * over a video and returns, per frame, boxes with a track id, a score and a class. This module
 * turns that result into tracks the workspace can preview, and the kept tracks into the rows the
 * save queue persists (one entity per track, one tracklet per contiguous run, one bbox per kept
 * frame, built in `trackingByDetectionRows`). This module imports no store: everything it needs
 * comes in as arguments, so the session reducers and the preview can use it freely.
 */

import type { BBox, Entity, Tracklet } from "$lib/types/dataset";
import type { VideoTrackedFrame, VideoTrackingTaskInput } from "$lib/types/inference";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export interface TrackingFrameSource {
  frameIndex: number;
  frameId: string;
  width: number;
  height: number;
}

export interface DetectionTrackFrame {
  frameIndex: number;
  frameId: string;
  /** Normalized x, y, width, height. */
  coords: [number, number, number, number];
  score: number;
  className: string | null;
}

export interface DetectionTrack {
  trackId: number;
  /** The class the model gave the object most often. */
  className: string | null;
  /** Sorted by frame index, one entry per frame the model saw the object in. */
  frames: DetectionTrackFrame[];
  startFrame: number;
  endFrame: number;
  meanScore: number;
  detectionCount: number;
}

/** A contiguous run of a track: one tracklet once saved. */
export interface DetectionTrackSegment {
  startFrame: number;
  endFrame: number;
  frames: DetectionTrackFrame[];
}

export interface TrackingByDetectionParams {
  /** Classes to follow; empty means the model's own set. */
  classes: string[];
  boxThreshold: number;
  fromCurrentFrame: boolean;
  /** Keep one box every N frames (plus the first and last of each run); 1 keeps them all. */
  keyframeStride: number;
  /** Frames a track may be missing before its next sighting starts a new tracklet. */
  maxGapFrames: number;
}

export const DEFAULT_TRACKING_BY_DETECTION_PARAMS: TrackingByDetectionParams = {
  classes: [],
  boxThreshold: 0.5,
  fromCurrentFrame: false,
  keyframeStride: 5,
  maxGapFrames: 30,
};

export interface TrackingWindow {
  startFrameIndex: number;
  endFrameIndex: number;
  frameCount: number;
}

export interface CollectedDetectionTracks {
  tracks: DetectionTrack[];
  skipped: { noBox: number; unknownFrame: number };
}

export interface DetectionRowEstimate {
  entities: number;
  tracklets: number;
  bboxes: number;
}

export interface TrackingByDetectionRows {
  entities: Entity[];
  tracklets: Tracklet[];
  bboxes: BBox[];
  /** Class values given to the label field, for the feature value lists. */
  classValues: string[];
}

export interface TrackingByDetectionRowsInput {
  tracks: DetectionTrack[];
  params: TrackingByDetectionParams;
  itemId: string;
  viewName: string;
  manifest: WorkspaceManifest;
  /** Entity field that receives the class, or null to keep it in the provenance only. */
  labelField: string | null;
  source: { modelName: string; providerName: string };
  frameSize: { width: number; height: number };
}

function sortedSources(sources: TrackingFrameSource[]): TrackingFrameSource[] {
  return [...sources].sort((left, right) => left.frameIndex - right.frameIndex);
}

/** The frames a run covers: the whole view, or from `fromFrameIndex` to its end. */
export function resolveTrackingWindow(
  sources: TrackingFrameSource[],
  fromFrameIndex: number | null,
): TrackingWindow | null {
  const frames = sortedSources(sources).filter(
    (source) => fromFrameIndex === null || source.frameIndex >= fromFrameIndex,
  );
  if (frames.length === 0) return null;
  return {
    startFrameIndex: frames[0].frameIndex,
    endFrameIndex: frames[frames.length - 1].frameIndex,
    frameCount: frames.length,
  };
}

export function buildTrackingByDetectionRequest(input: {
  model: string;
  providerName: string;
  datasetId: string;
  recordId: string;
  viewName: string;
  window: TrackingWindow;
  classes: string[];
  boxThreshold: number;
}): VideoTrackingTaskInput {
  // A prompt-free request names no object: the model decides what to follow.
  return {
    model: input.model,
    provider_name: input.providerName,
    dataset_id: input.datasetId,
    record_id: input.recordId,
    view_name: input.viewName,
    start_frame_index: input.window.startFrameIndex,
    frame_count: input.window.frameCount,
    objects_ids: [],
    prompt_frame_indexes: [],
    propagate: true,
    classes: input.classes.length > 0 ? input.classes : null,
    box_threshold: input.boxThreshold,
  };
}

/** Class names typed by hand: one per comma or line, trimmed, without duplicates. */
export function parseClassList(text: string): string[] {
  const seen = new Set<string>();
  const classes: string[] = [];
  for (const raw of text.split(/[,\n]/)) {
    const name = raw.trim();
    if (name.length === 0 || seen.has(name)) continue;
    seen.add(name);
    classes.push(name);
  }
  return classes;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function majorityClass(frames: DetectionTrackFrame[]): string | null {
  const counts = new Map<string, number>();
  for (const frame of frames) {
    if (frame.className === null) continue;
    counts.set(frame.className, (counts.get(frame.className) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [name, count] of counts) {
    if (count > bestCount) {
      best = name;
      bestCount = count;
    }
  }
  return best;
}

/**
 * Group the model's per-frame objects by track. Boxes come as [x1, y1, x2, y2] pixels and are
 * normalized by the frame they belong to; masks are ignored; an object without a box, or in a
 * frame the window does not know, is skipped and counted.
 */
export function collectDetectionTracks(
  frames: VideoTrackedFrame[],
  sources: TrackingFrameSource[],
): CollectedDetectionTracks {
  const sourceByIndex = new Map(sources.map((source) => [source.frameIndex, source]));
  const framesByTrack = new Map<number, Map<number, DetectionTrackFrame>>();
  const skipped = { noBox: 0, unknownFrame: 0 };

  for (const frame of frames) {
    const source = sourceByIndex.get(frame.frame_index);
    for (const tracked of frame.objects) {
      if (!source) {
        skipped.unknownFrame += 1;
        continue;
      }
      const box = tracked.box;
      if (!box || box.length !== 4 || box.some((value) => !Number.isFinite(value))) {
        skipped.noBox += 1;
        continue;
      }
      const [x1, y1, x2, y2] = box;
      const detection: DetectionTrackFrame = {
        frameIndex: frame.frame_index,
        frameId: source.frameId,
        coords: [
          clamp01(x1 / source.width),
          clamp01(y1 / source.height),
          clamp01((x2 - x1) / source.width),
          clamp01((y2 - y1) / source.height),
        ],
        score: tracked.score ?? 1,
        className: tracked.class_name ?? null,
      };
      const byFrame = framesByTrack.get(tracked.track_id) ?? new Map<number, DetectionTrackFrame>();
      const existing = byFrame.get(frame.frame_index);
      if (!existing || existing.score < detection.score) {
        byFrame.set(frame.frame_index, detection);
      }
      framesByTrack.set(tracked.track_id, byFrame);
    }
  }

  const tracks: DetectionTrack[] = [];
  for (const [trackId, byFrame] of framesByTrack) {
    const trackFrames = [...byFrame.values()].sort(
      (left, right) => left.frameIndex - right.frameIndex,
    );
    const scoreSum = trackFrames.reduce((sum, frame) => sum + frame.score, 0);
    tracks.push({
      trackId,
      className: majorityClass(trackFrames),
      frames: trackFrames,
      startFrame: trackFrames[0].frameIndex,
      endFrame: trackFrames[trackFrames.length - 1].frameIndex,
      meanScore: scoreSum / trackFrames.length,
      detectionCount: trackFrames.length,
    });
  }
  tracks.sort((left, right) => left.startFrame - right.startFrame || left.trackId - right.trackId);
  return { tracks, skipped };
}

/** Whole tracks pass or fail on their mean score; each box keeps its own score. */
export function applyScoreThreshold(tracks: DetectionTrack[], threshold: number): DetectionTrack[] {
  return tracks.filter((track) => track.meanScore >= threshold);
}

export function splitTrackIntoSegments(
  track: DetectionTrack,
  maxGapFrames: number,
): DetectionTrackSegment[] {
  const segments: DetectionTrackSegment[] = [];
  let current: DetectionTrackFrame[] = [];
  for (const frame of track.frames) {
    const previous = current[current.length - 1];
    if (previous && frame.frameIndex - previous.frameIndex > maxGapFrames) {
      segments.push(toSegment(current));
      current = [];
    }
    current.push(frame);
  }
  if (current.length > 0) segments.push(toSegment(current));
  return segments;
}

function toSegment(frames: DetectionTrackFrame[]): DetectionTrackSegment {
  return {
    startFrame: frames[0].frameIndex,
    endFrame: frames[frames.length - 1].frameIndex,
    frames,
  };
}

/** The boxes of a run that are saved: the first, every `stride`-th after it, and the last. */
export function applyKeyframeStride(
  segment: DetectionTrackSegment,
  stride: number,
): DetectionTrackFrame[] {
  const step = Math.max(1, Math.floor(stride));
  const last = segment.frames.length - 1;
  return segment.frames.filter(
    (frame, index) =>
      index === 0 || index === last || (frame.frameIndex - segment.startFrame) % step === 0,
  );
}

/** Linear interpolation between the kept boxes, as the workspace will display the saved tracklet. */
export function interpolateSegmentAt(
  keyframes: DetectionTrackFrame[],
  frameIndex: number,
): { coords: [number, number, number, number]; isKeyframe: boolean } | null {
  if (keyframes.length === 0) return null;
  const exact = keyframes.find((frame) => frame.frameIndex === frameIndex);
  if (exact) return { coords: exact.coords, isKeyframe: true };
  if (
    frameIndex < keyframes[0].frameIndex ||
    frameIndex > keyframes[keyframes.length - 1].frameIndex
  ) {
    return null;
  }
  let before = keyframes[0];
  let after = keyframes[keyframes.length - 1];
  for (const frame of keyframes) {
    if (frame.frameIndex < frameIndex) before = frame;
    if (frame.frameIndex > frameIndex) {
      after = frame;
      break;
    }
  }
  const span = after.frameIndex - before.frameIndex;
  const t = span === 0 ? 0 : (frameIndex - before.frameIndex) / span;
  const coords = before.coords.map((value, index) => value + (after.coords[index] - value) * t) as [
    number,
    number,
    number,
    number,
  ];
  return { coords, isKeyframe: false };
}

export function estimateTrackingByDetectionRows(
  tracks: DetectionTrack[],
  params: TrackingByDetectionParams,
): DetectionRowEstimate {
  let tracklets = 0;
  let bboxes = 0;
  for (const track of tracks) {
    for (const segment of splitTrackIntoSegments(track, params.maxGapFrames)) {
      tracklets += 1;
      bboxes += applyKeyframeStride(segment, params.keyframeStride).length;
    }
  }
  return { entities: tracks.length, tracklets, bboxes };
}
