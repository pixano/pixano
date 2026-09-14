/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { isTerminal, progressOf } from "../jobs.svelte";
import type { Job } from "$lib/api/jobs";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "j1",
    kind: "fake",
    dataset: "ds",
    state: "running",
    total_tasks: 200,
    done_tasks: 50,
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
