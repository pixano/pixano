/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * State of a tracking-by-detection session, as pure reducers: setup (the run form), running (one
 * inference job), review (preview tracks the user keeps or discards), error. A result or a
 * failure only counts for the request that is still current.
 */

import {
  DEFAULT_TRACKING_BY_DETECTION_PARAMS,
  type DetectionTrack,
  type TrackingByDetectionParams,
} from "$lib/tracking/trackingByDetection";

export type TrackingByDetectionPhase = "idle" | "setup" | "running" | "review" | "error";

export interface TrackingByDetectionRun {
  requestId: string;
  jobId: string | null;
  viewName: string;
  startFrameIndex: number;
  endFrameIndex: number;
  frameCount: number;
  model: string;
  providerName: string;
}

export interface DetectionSkippedObjects {
  noBox: number;
  unknownFrame: number;
}

export interface TrackingByDetectionTarget {
  datasetId: string;
  recordId: string;
}

export interface TrackingByDetectionSessionState {
  phase: TrackingByDetectionPhase;
  params: TrackingByDetectionParams;
  target: TrackingByDetectionTarget | null;
  viewName: string | null;
  run: TrackingByDetectionRun | null;
  tracks: DetectionTrack[];
  discardedTrackIds: number[];
  reviewThreshold: number;
  selectedTrackId: number | null;
  skipped: DetectionSkippedObjects;
  error: string | null;
}

export const NULL_TRACKING_BY_DETECTION_STATE: TrackingByDetectionSessionState = {
  phase: "idle",
  params: { ...DEFAULT_TRACKING_BY_DETECTION_PARAMS },
  target: null,
  viewName: null,
  run: null,
  tracks: [],
  discardedTrackIds: [],
  reviewThreshold: DEFAULT_TRACKING_BY_DETECTION_PARAMS.boxThreshold,
  selectedTrackId: null,
  skipped: { noBox: 0, unknownFrame: 0 },
  error: null,
};

export function openSetupState(
  state: TrackingByDetectionSessionState,
  target: TrackingByDetectionTarget,
  viewName: string,
): TrackingByDetectionSessionState {
  return {
    ...NULL_TRACKING_BY_DETECTION_STATE,
    phase: "setup",
    params: { ...state.params },
    target,
    viewName,
  };
}

/** Switch the view a run will cover (multi-view videos); only meaningful before a run. */
export function selectViewState(
  state: TrackingByDetectionSessionState,
  viewName: string,
): TrackingByDetectionSessionState {
  if (state.phase !== "setup" && state.phase !== "error") return state;
  return { ...state, viewName };
}

export function updateParamsState(
  state: TrackingByDetectionSessionState,
  patch: Partial<TrackingByDetectionParams>,
): TrackingByDetectionSessionState {
  return { ...state, params: { ...state.params, ...patch } };
}

export function beginRunState(
  state: TrackingByDetectionSessionState,
  run: TrackingByDetectionRun,
): TrackingByDetectionSessionState {
  return {
    ...state,
    phase: "running",
    viewName: run.viewName,
    run,
    tracks: [],
    discardedTrackIds: [],
    selectedTrackId: null,
    skipped: { noBox: 0, unknownFrame: 0 },
    error: null,
  };
}

function isCurrentRun(state: TrackingByDetectionSessionState, requestId: string): boolean {
  return state.phase === "running" && state.run?.requestId === requestId;
}

export function attachJobState(
  state: TrackingByDetectionSessionState,
  requestId: string,
  jobId: string | null,
): TrackingByDetectionSessionState {
  if (!isCurrentRun(state, requestId) || !state.run) return state;
  return { ...state, run: { ...state.run, jobId } };
}

export function completeRunState(
  state: TrackingByDetectionSessionState,
  requestId: string,
  tracks: DetectionTrack[],
  skipped: DetectionSkippedObjects,
): TrackingByDetectionSessionState {
  if (!isCurrentRun(state, requestId)) return state;
  return {
    ...state,
    phase: "review",
    tracks,
    skipped,
    discardedTrackIds: [],
    reviewThreshold: state.params.boxThreshold,
    selectedTrackId: null,
    error: null,
  };
}

export function failRunState(
  state: TrackingByDetectionSessionState,
  requestId: string,
  message: string,
): TrackingByDetectionSessionState {
  if (!isCurrentRun(state, requestId)) return state;
  return { ...state, phase: "error", run: null, error: message };
}

/** Back to the form, parameters kept. */
export function cancelRunState(
  state: TrackingByDetectionSessionState,
): TrackingByDetectionSessionState {
  if (state.phase === "idle") return state;
  return { ...state, phase: "setup", run: null, tracks: [], selectedTrackId: null, error: null };
}

export function toggleTrackDiscardState(
  state: TrackingByDetectionSessionState,
  trackId: number,
): TrackingByDetectionSessionState {
  const discarded = state.discardedTrackIds.includes(trackId)
    ? state.discardedTrackIds.filter((id) => id !== trackId)
    : [...state.discardedTrackIds, trackId];
  return { ...state, discardedTrackIds: discarded };
}

export function setReviewThresholdState(
  state: TrackingByDetectionSessionState,
  threshold: number,
): TrackingByDetectionSessionState {
  return { ...state, reviewThreshold: Math.min(1, Math.max(0, threshold)) };
}

export function selectTrackState(
  state: TrackingByDetectionSessionState,
  trackId: number | null,
): TrackingByDetectionSessionState {
  return { ...state, selectedTrackId: trackId };
}

export function isTrackingByDetectionActiveState(state: TrackingByDetectionSessionState): boolean {
  return state.phase !== "idle";
}
