/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { isTerminal, outcomeOf, progressOf } from "../jobs.svelte";
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
