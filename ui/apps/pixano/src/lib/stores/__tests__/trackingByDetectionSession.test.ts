/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

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
  setReviewThresholdState,
  toggleTrackDiscardState,
  updateParamsState,
  type TrackingByDetectionRun,
} from "../trackingByDetectionSession";
import type { DetectionTrack } from "$lib/tracking/trackingByDetection";

const run: TrackingByDetectionRun = {
  requestId: "r1",
  jobId: null,
  viewName: "image",
  startFrameIndex: 0,
  endFrameIndex: 9,
  frameCount: 10,
  model: "yolo-bytetrack",
  providerName: "pixano-inference",
};

const target = { datasetId: "dataset-1", recordId: "record-1" };

const track = (trackId: number): DetectionTrack => ({
  trackId,
  className: "person",
  frames: [],
  startFrame: 0,
  endFrame: 0,
  meanScore: 0.9,
  detectionCount: 1,
});

describe("tracking-by-detection session", () => {
  it("goes setup → running → review, keeping the parameters and resetting the threshold", () => {
    let state = openSetupState(NULL_TRACKING_BY_DETECTION_STATE, target, "image");
    expect(isTrackingByDetectionActiveState(NULL_TRACKING_BY_DETECTION_STATE)).toBe(false);
    expect(isTrackingByDetectionActiveState(state)).toBe(true);
    state = updateParamsState(state, { classes: ["person"], boxThreshold: 0.3 });

    state = beginRunState(state, run);
    expect(state.phase).toBe("running");
    state = attachJobState(state, "r1", "job-1");
    expect(state.run?.jobId).toBe("job-1");

    state = completeRunState(state, "r1", [track(1), track(2)], { noBox: 1, unknownFrame: 0 });
    expect(state.phase).toBe("review");
    expect(state.tracks).toHaveLength(2);
    expect(state.reviewThreshold).toBe(0.3);
    expect(state.params.classes).toEqual(["person"]);
    expect(state.skipped.noBox).toBe(1);

    // A new setup from the review keeps the parameters but drops the result.
    const again = openSetupState(state, target, "image");
    expect(again.target).toEqual(target);
    expect(again.params.classes).toEqual(["person"]);
    expect(again.tracks).toEqual([]);
  });

  it("ignores results and failures of a request that is no longer current", () => {
    let state = beginRunState(
      openSetupState(NULL_TRACKING_BY_DETECTION_STATE, target, "image"),
      run,
    );
    expect(completeRunState(state, "stale", [track(1)], { noBox: 0, unknownFrame: 0 })).toBe(state);
    expect(failRunState(state, "stale", "boom")).toBe(state);
    expect(attachJobState(state, "stale", "job-x").run?.jobId).toBeNull();

    state = failRunState(state, "r1", "boom");
    expect(state.phase).toBe("error");
    expect(state.error).toBe("boom");
    expect(state.run).toBeNull();
  });

  it("cancels back to the form and reviews with discard, threshold and selection", () => {
    let state = beginRunState(
      openSetupState(NULL_TRACKING_BY_DETECTION_STATE, target, "image"),
      run,
    );
    expect(cancelRunState(state).phase).toBe("setup");
    expect(cancelRunState(NULL_TRACKING_BY_DETECTION_STATE)).toBe(NULL_TRACKING_BY_DETECTION_STATE);

    state = completeRunState(state, "r1", [track(1), track(2)], { noBox: 0, unknownFrame: 0 });
    state = toggleTrackDiscardState(state, 2);
    expect(state.discardedTrackIds).toEqual([2]);
    state = toggleTrackDiscardState(state, 2);
    expect(state.discardedTrackIds).toEqual([]);
    expect(setReviewThresholdState(state, 1.4).reviewThreshold).toBe(1);
    expect(selectTrackState(state, 1).selectedTrackId).toBe(1);
    expect(selectTrackState(state, null).selectedTrackId).toBeNull();
  });
});
