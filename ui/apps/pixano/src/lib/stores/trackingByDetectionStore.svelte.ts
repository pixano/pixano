/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Tracking by detection in the video workspace: a prompt-free tracking model runs over the video
 * as one inference job; its tracks are previewed on the canvas and the timeline, reviewed, and the
 * kept ones are turned into rows by the accept step. The session is reduced by
 * `trackingByDetectionSession`; this module adds the job run, the frame sources and what the
 * canvas and the timeline derive from the session.
 */

import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import {
  attachJobState,
  beginRunState,
  cancelRunState,
  completeRunState,
  failRunState,
  isTrackingByDetectionActiveState,
  NULL_TRACKING_BY_DETECTION_STATE,
  openSetupState,
  selectTrackState,
  selectViewState,
  setReviewThresholdState,
  toggleTrackDiscardState,
  updateParamsState,
  type TrackingByDetectionRun,
  type TrackingByDetectionSessionState,
  type TrackingByDetectionTarget,
} from "./trackingByDetectionSession";
import { cancelTrackingSession, createPreviewBBox, resetVosSession } from "./trackingStore.svelte";
import { currentFrameIndex } from "./videoStores.svelte";
import { selectedTool, views } from "./workspaceBaseStores.svelte";
import { ApiError } from "$lib/api/apiClient";
import { cancelTrackingJob, getTrackingJob, submitTrackingJob } from "$lib/api/inferenceApi";
import { panTool } from "$lib/tools";
import {
  applyKeyframeStride,
  applyScoreThreshold,
  buildTrackingByDetectionRequest,
  collectDetectionTracks,
  estimateTrackingByDetectionRows,
  interpolateSegmentAt,
  resolveTrackingWindow,
  splitTrackIntoSegments,
  type DetectionTrack,
  type DetectionTrackFrame,
  type TrackingByDetectionParams,
  type TrackingFrameSource,
} from "$lib/tracking/trackingByDetection";
import { createTrackingJobRunner } from "$lib/tracking/trackingJobRunner";
import {
  buildDetectionTimelineLanes,
  type DetectionTimelineLane,
  type TrackingTimelineState,
} from "$lib/trackingTimeline";
import type { BBox, SequenceFrame } from "$lib/types/dataset";
import type {
  InferenceModelSelection,
  VideoTrackingJobStatus,
  VideoTrackingTaskInput,
} from "$lib/types/inference";
import { paletteColorAt } from "$lib/utils/coreUtils";

export type { TrackingByDetectionSessionState } from "./trackingByDetectionSession";

export interface TrackingByDetectionApi {
  submit: (input: VideoTrackingTaskInput) => Promise<VideoTrackingJobStatus>;
  getStatus: (jobId: string) => Promise<VideoTrackingJobStatus>;
  cancel: (jobId: string) => Promise<unknown>;
}

const defaultApi: TrackingByDetectionApi = {
  submit: submitTrackingJob,
  getStatus: getTrackingJob,
  cancel: cancelTrackingJob,
};
let api: TrackingByDetectionApi = defaultApi;

/** Tests inject the job API; `null` restores the real one. */
export function setTrackingByDetectionApi(next: TrackingByDetectionApi | null): void {
  api = next ?? defaultApi;
}

export const trackingByDetectionSession = reactiveStore<TrackingByDetectionSessionState>({
  ...NULL_TRACKING_BY_DETECTION_STATE,
});

const runner = createTrackingJobRunner({
  onActiveChange: (active) => {
    if (!active) return;
    trackingByDetectionSession.update((state) =>
      attachJobState(state, active.requestId, active.jobId),
    );
  },
});

export const DETECTION_TRACK_ID_PREFIX = "detection-track-";

export function detectionTrackEntityId(trackId: number): string {
  return `${DETECTION_TRACK_ID_PREFIX}${trackId}`;
}

// ─── Frame sources ──────────────────────────────────────────────────────────

/**
 * The frames of a view as the run needs them. A frame without dimensions borrows those of the
 * first frame that has some; a view where none has any cannot place boxes, which the run refuses.
 */
export function resolveTrackingFrameSources(viewName: string): TrackingFrameSource[] {
  const frames = views.value[viewName];
  if (!Array.isArray(frames)) return [];
  const sources = (frames as SequenceFrame[]).map((frame) => ({
    frameIndex: Number(frame.data.frame_index),
    frameId: frame.id,
    width: Number(frame.data.width),
    height: Number(frame.data.height),
  }));
  const known = sources.find((source) => source.width > 0 && source.height > 0);
  return sources
    .map((source) =>
      source.width > 0 && source.height > 0
        ? source
        : { ...source, width: known?.width ?? 0, height: known?.height ?? 0 },
    )
    .sort((left, right) => left.frameIndex - right.frameIndex);
}

// ─── Actions ────────────────────────────────────────────────────────────────

/** Open the run form. The bbox and VOS sessions cannot run alongside: they are reset. */
export function openTrackingByDetectionSetup(
  target: TrackingByDetectionTarget,
  viewName: string,
): void {
  cancelTrackingSession();
  resetVosSession();
  selectedTool.value = panTool;
  trackingByDetectionSession.update((state) => openSetupState(state, target, viewName));
}

export function selectTrackingByDetectionView(viewName: string): void {
  trackingByDetectionSession.update((state) => selectViewState(state, viewName));
}

export function resetTrackingByDetectionSession(): void {
  if (!isTrackingByDetectionActiveState(trackingByDetectionSession.value)) return;
  void runner.cancelActive();
  trackingByDetectionSession.value = {
    ...NULL_TRACKING_BY_DETECTION_STATE,
    params: { ...trackingByDetectionSession.value.params },
  };
}

export function updateTrackingByDetectionParams(patch: Partial<TrackingByDetectionParams>): void {
  trackingByDetectionSession.update((state) => updateParamsState(state, patch));
}

export interface TrackingByDetectionRunContext {
  datasetId: string;
  recordId: string;
  viewName: string;
  model: InferenceModelSelection;
}

/** Start a run on the session's own target and view (what the inspector panel does). */
export async function startTrackingByDetectionRunHere(
  model: InferenceModelSelection,
): Promise<void> {
  const { target, viewName } = trackingByDetectionSession.value;
  if (!target || !viewName) return;
  await startTrackingByDetectionRun({ ...target, viewName, model });
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const body = JSON.parse(error.body) as { detail?: string | { message?: string } };
      const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
      if (detail) return detail;
    } catch {
      // Not JSON: fall through to the generic message.
    }
    return `Tracking failed (${error.status}).`;
  }
  return error instanceof Error ? error.message : "Tracking failed.";
}

export async function startTrackingByDetectionRun(
  context: TrackingByDetectionRunContext,
): Promise<void> {
  const { params } = trackingByDetectionSession.value;
  const sources = resolveTrackingFrameSources(context.viewName);
  const window = resolveTrackingWindow(
    sources,
    params.fromCurrentFrame ? currentFrameIndex.value : null,
  );
  const requestId = `detection-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const run: TrackingByDetectionRun = {
    requestId,
    jobId: null,
    viewName: context.viewName,
    startFrameIndex: window?.startFrameIndex ?? 0,
    endFrameIndex: window?.endFrameIndex ?? 0,
    frameCount: window?.frameCount ?? 0,
    model: context.model.name,
    providerName: context.model.provider_name,
  };
  const fail = (message: string) =>
    trackingByDetectionSession.update((state) => failRunState(state, requestId, message));

  trackingByDetectionSession.update((state) => beginRunState(state, run));
  if (!window) {
    fail("No frames to track in this view.");
    return;
  }
  if (sources.some((source) => !(source.width > 0 && source.height > 0))) {
    fail("The frame dimensions of this view are unknown; the boxes could not be placed.");
    return;
  }

  const request = buildTrackingByDetectionRequest({
    model: context.model.name,
    providerName: context.model.provider_name,
    datasetId: context.datasetId,
    recordId: context.recordId,
    viewName: context.viewName,
    window,
    classes: params.classes,
    boxThreshold: params.boxThreshold,
  });

  try {
    const status = await runner.run({
      requestId,
      kind: "detection",
      viewName: context.viewName,
      submit: () => api.submit(request),
      getStatus: (jobId) => api.getStatus(jobId),
      cancel: (jobId) => api.cancel(jobId),
    });
    if (!status) {
      // Superseded or cancelled: whoever did it already moved the session on.
      return;
    }
    if (status.status !== "completed") {
      fail(status.detail ?? "Tracking job failed.");
      return;
    }
    const { tracks, skipped } = collectDetectionTracks(status.data?.frames ?? [], sources);
    trackingByDetectionSession.update((state) =>
      completeRunState(state, requestId, tracks, skipped),
    );
  } catch (error) {
    fail(describeError(error));
  }
}

export async function cancelTrackingByDetectionRun(): Promise<void> {
  await runner.cancelActive();
  trackingByDetectionSession.update(cancelRunState);
}

export function toggleDetectionTrackDiscard(trackId: number): void {
  trackingByDetectionSession.update((state) => toggleTrackDiscardState(state, trackId));
}

export function setDetectionReviewThreshold(threshold: number): void {
  trackingByDetectionSession.update((state) => setReviewThresholdState(state, threshold));
}

export function selectDetectionTrack(trackId: number | null): void {
  trackingByDetectionSession.update((state) => selectTrackState(state, trackId));
}

// ─── Derived ────────────────────────────────────────────────────────────────

export const isTrackingByDetectionActive = reactiveDerived(() =>
  isTrackingByDetectionActiveState(trackingByDetectionSession.value),
);

export const visibleDetectionTracks = reactiveDerived<DetectionTrack[]>(() => {
  const state = trackingByDetectionSession.value;
  return applyScoreThreshold(state.tracks, state.reviewThreshold);
});

export const keptDetectionTracks = reactiveDerived<DetectionTrack[]>(() => {
  const discarded = new Set(trackingByDetectionSession.value.discardedTrackIds);
  return visibleDetectionTracks.value.filter((track) => !discarded.has(track.trackId));
});

/** One palette colour per proposed track, keyed by the synthetic entity id of its preview boxes. */
export const detectionTrackColorById = reactiveDerived<Map<string, string>>(() => {
  return new Map(
    trackingByDetectionSession.value.tracks.map((track, index) => [
      detectionTrackEntityId(track.trackId),
      paletteColorAt(index),
    ]),
  );
});

/** The boxes that would be saved, per run of each track: what the preview interpolates between. */
const detectionKeyframesByTrack = reactiveDerived<Map<number, DetectionTrackFrame[][]>>(() => {
  const { tracks, params } = trackingByDetectionSession.value;
  return new Map(
    tracks.map((track) => [
      track.trackId,
      splitTrackIntoSegments(track, params.maxGapFrames).map((segment) =>
        applyKeyframeStride(segment, params.keyframeStride),
      ),
    ]),
  );
});

export const trackingByDetectionPreviewBBoxes = reactiveDerived<BBox[]>(() => {
  const state = trackingByDetectionSession.value;
  if (state.phase !== "review" || !state.viewName) return [];
  const frameIndex = currentFrameIndex.value;
  const source = resolveTrackingFrameSources(state.viewName).find(
    (candidate) => candidate.frameIndex === frameIndex,
  );
  if (!source) return [];

  const discarded = new Set(state.discardedTrackIds);
  const boxes: BBox[] = [];
  for (const track of visibleDetectionTracks.value) {
    for (const keyframes of detectionKeyframesByTrack.value.get(track.trackId) ?? []) {
      const result = interpolateSegmentAt(keyframes, frameIndex);
      if (!result) continue;
      const isDiscarded = discarded.has(track.trackId);
      const isSelected = state.selectedTrackId === track.trackId;
      boxes.push(
        createPreviewBBox({
          id: `detection-preview-${track.trackId}-${frameIndex}`,
          viewName: state.viewName,
          frameId: source.frameId,
          frameIndex,
          coords: result.coords,
          imageWidth: source.width,
          imageHeight: source.height,
          entityId: detectionTrackEntityId(track.trackId),
          highlighted: isSelected ? "self" : isDiscarded ? "none" : "all",
          opacity: isDiscarded ? 0.3 : result.isKeyframe ? 1 : 0.7,
          strokeFactor: isSelected ? 2.5 : result.isKeyframe ? 2 : 1,
          tooltip: `${track.className ?? "object"} #${track.trackId} · ${Math.round(track.meanScore * 100)}%${
            isDiscarded ? " (discarded)" : ""
          }`,
        }),
      );
      break;
    }
  }
  return boxes;
});

export const trackingByDetectionTimelineState = reactiveDerived<TrackingTimelineState | null>(
  () => {
    const state = trackingByDetectionSession.value;
    if (state.phase !== "running" || !state.run) return null;
    return {
      variant: "detection",
      segments: [],
      keyframes: [],
      pendingMarkerIndex: null,
      pendingInterval: [state.run.startFrameIndex, state.run.endFrameIndex],
    };
  },
);

export const detectionTimelineLanes = reactiveDerived<DetectionTimelineLane[]>(() => {
  const state = trackingByDetectionSession.value;
  if (state.phase !== "review") return [];
  const colors = detectionTrackColorById.value;
  return buildDetectionTimelineLanes(visibleDetectionTracks.value, {
    discardedTrackIds: state.discardedTrackIds,
    selectedTrackId: state.selectedTrackId,
    maxGapFrames: state.params.maxGapFrames,
    colorOf: (trackId) => colors.get(detectionTrackEntityId(trackId)) ?? paletteColorAt(0),
  });
});

export const trackingByDetectionRowEstimate = reactiveDerived(() =>
  estimateTrackingByDetectionRows(
    keptDetectionTracks.value,
    trackingByDetectionSession.value.params,
  ),
);
