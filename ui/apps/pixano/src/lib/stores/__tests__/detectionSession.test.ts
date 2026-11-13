/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  beginRunState,
  closeState,
  completeRunState,
  failRunState,
  isDetectionActiveState,
  NULL_DETECTION_STATE,
  openSetupState,
  resetState,
  selectViewState,
  updateParamsState,
} from "../detectionSession";
import type { SessionProposal } from "$lib/detection/detection";

const target = { datasetId: "dataset-1", recordId: "record-1" };
const proposal: SessionProposal = { bboxId: "b1", viewName: "image", box: [1, 2, 3, 4] };
const summary = { found: 2, added: 1, duplicates: 1, exemplars: 3, negatives: 0 };

describe("detection session", () => {
  it("opens, runs, and remembers the proposals it added", () => {
    let state = openSetupState(NULL_DETECTION_STATE, target, "image");
    expect(isDetectionActiveState(state)).toBe(true);
    state = beginRunState(state, "r1");
    expect(state.phase).toBe("running");
    state = completeRunState(state, "r1", [proposal], summary);
    expect(state.phase).toBe("setup");
    expect(state.proposals).toEqual([proposal]);
    expect(state.lastRun).toEqual(summary);
  });

  it("ignores the result of a run superseded or cancelled", () => {
    const running = beginRunState(openSetupState(NULL_DETECTION_STATE, target, "image"), "r1");
    expect(completeRunState(running, "r0", [proposal], summary)).toBe(running);
    const closed = closeState(running);
    expect(completeRunState(closed, "r1", [proposal], summary)).toBe(closed);
    expect(failRunState(running, "r0", "late")).toBe(running);
  });

  it("does not start a second run, nor one while closed", () => {
    const running = beginRunState(openSetupState(NULL_DETECTION_STATE, target, "image"), "r1");
    expect(beginRunState(running, "r2")).toBe(running);
    expect(beginRunState(NULL_DETECTION_STATE, "r1")).toBe(NULL_DETECTION_STATE);
  });

  it("reports a failure and lets the user run again", () => {
    let state = beginRunState(openSetupState(NULL_DETECTION_STATE, target, "image"), "r1");
    state = failRunState(state, "r1", "Model 'gdino' does not take exemplar boxes.");
    expect(state.phase).toBe("error");
    expect(state.error).toContain("exemplar");
    expect(beginRunState(state, "r2").phase).toBe("running");
  });

  it("keeps the proposals when closed and reopened on the record, drops them for another", () => {
    let state = completeRunState(
      beginRunState(openSetupState(NULL_DETECTION_STATE, target, "image"), "r1"),
      "r1",
      [proposal],
      summary,
    );
    state = updateParamsState(state, { className: "screw" });
    state = openSetupState(closeState(state), target, "image");
    expect(state.proposals).toEqual([proposal]);

    const other = openSetupState(state, { ...target, recordId: "record-2" }, "image");
    expect(other.proposals).toEqual([]);
    expect(other.params.className).toBe("screw");

    const reset = resetState(state);
    expect(reset.phase).toBe("closed");
    expect(reset.proposals).toEqual([]);
    expect(reset.params.className).toBe("screw");
  });

  it("switches view between runs only", () => {
    const setup = openSetupState(NULL_DETECTION_STATE, target, "left");
    expect(selectViewState(setup, "right").viewName).toBe("right");
    const running = beginRunState(setup, "r1");
    expect(selectViewState(running, "right")).toBe(running);
  });
});
