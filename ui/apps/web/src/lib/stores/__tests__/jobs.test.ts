/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  canCancel,
  failureOf,
  isTerminal,
  outcomeOf,
  progressOf,
  recordOf,
  stateLabelOf,
} from "../jobs.svelte";
import type { Job } from "$lib/api/jobs";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "j1",
    kind: "fake",
    dataset: "ds",
    state: "running",
    total_tasks: 200,
    done_tasks: 50,
    produced: 0,
    skipped: 0,
    quarantined: 0,
    cancel_requested: false,
    error: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("progressOf", () => {
  it("is the share of tasks finished", () => {
    expect(progressOf(job({ done_tasks: 50, total_tasks: 200 }))).toBe(0.25);
  });

  it("is zero while the total is unknown", () => {
    // A job being planned has no denominator yet: the worker is still deciding how much
    // work there is, so anything but zero would be invented.
    expect(progressOf(job({ state: "planning", total_tasks: 0, done_tasks: 0 }))).toBe(0);
  });

  it("never exceeds one", () => {
    // Guards the bar against a counter that ever runs ahead of its total.
    expect(progressOf(job({ done_tasks: 250, total_tasks: 200 }))).toBe(1);
  });

  it("is one when everything is done", () => {
    expect(progressOf(job({ done_tasks: 200, total_tasks: 200 }))).toBe(1);
  });
});

describe("isTerminal", () => {
  it("recognises the states nobody is waiting on", () => {
    expect(isTerminal("done")).toBe(true);
    expect(isTerminal("error")).toBe(true);
    expect(isTerminal("cancelled")).toBe(true);
  });

  it("leaves a job in flight alone", () => {
    // This is what decides whether a Cancel button is shown at all.
    expect(isTerminal("planning")).toBe(false);
    expect(isTerminal("pending")).toBe(false);
    expect(isTerminal("running")).toBe(false);
  });
});

describe("outcomeOf", () => {
  it("says nothing while the job runs", () => {
    // Counts in flight would read as final; the progress bar is what speaks until the end.
    expect(outcomeOf(job({ state: "running", produced: 40 }))).toBeNull();
  });

  it("says what a finished job produced", () => {
    expect(outcomeOf(job({ state: "done", produced: 200 }))).toBe("200 produced");
  });

  it("names skipped and quarantined tasks when there are any", () => {
    // The nuScenes case: the bar reads full, and this line is what tells the truth.
    expect(outcomeOf(job({ state: "done", produced: 404, skipped: 26_361, quarantined: 1 }))).toBe(
      "404 produced · 26361 skipped · 1 quarantined",
    );
  });

  it("reports what a cancelled job had produced before it stopped", () => {
    expect(outcomeOf(job({ state: "cancelled", produced: 60 }))).toBe("60 produced");
  });
});

describe("stateLabelOf", () => {
  it("shows the state of a job nobody touched", () => {
    expect(stateLabelOf(job({ state: "running" }))).toBe("running");
  });

  it("says cancelling while the chunks in flight finish", () => {
    // Seen rehearsing the demo: the job read "running" for seconds after Cancel was clicked.
    expect(stateLabelOf(job({ state: "running", cancel_requested: true }))).toBe("cancelling");
  });

  it("shows the final state once the job has settled", () => {
    expect(stateLabelOf(job({ state: "cancelled", cancel_requested: true }))).toBe("cancelled");
  });
});

describe("canCancel", () => {
  it("offers to cancel a job in flight", () => {
    expect(canCancel(job({ state: "running" }))).toBe(true);
  });

  it("does not offer it twice", () => {
    expect(canCancel(job({ state: "running", cancel_requested: true }))).toBe(false);
  });

  it("does not offer it once the job has ended", () => {
    expect(canCancel(job({ state: "done" }))).toBe(false);
  });
});

describe("failureOf", () => {
  it("is silent for a job that did not fail", () => {
    expect(failureOf(job({ state: "done" }))).toBeNull();
  });

  it("adds the detail, which says why", () => {
    // Step 2, lot 1: a job refused at planning named the media types it could not process,
    // and the panel showed "planning failed" alone.
    const failed = job({
      state: "error",
      error: {
        reason: "planning failed",
        detail: "the 'embeddings' job cannot process point_cloud",
      },
    });
    expect(failureOf(failed)).toBe(
      "planning failed: the 'embeddings' job cannot process point_cloud",
    );
  });

  it("gives the reason of a failed job", () => {
    // Independent review, D4: a failed job read "error" and nothing else.
    expect(failureOf(job({ state: "error", error: { reason: "planning failed" } }))).toBe(
      "planning failed",
    );
  });

  it("says so when a failed job carries no reason", () => {
    expect(failureOf(job({ state: "error", error: null }))).toBe("failed for an unknown reason");
  });
});

describe("recordOf", () => {
  // Step 2, lot 1: a quarantined item is a medium; its record is what a user opens.
  const item = (detail: Record<string, unknown> | null) => ({
    item_id: "cam-front-42",
    reason: "refused by the inference server",
    detail,
    created_at: "",
  });

  it("names the record the job gave", () => {
    expect(recordOf(item({ record_id: "rec-42", status: 500 }))).toBe("rec-42");
  });

  it("is silent when the job gave none", () => {
    expect(recordOf(item(null))).toBeNull();
  });
});
