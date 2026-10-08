/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { createTrackingJobRunner, type ActiveTrackingJob } from "../trackingJobRunner";
import type { VideoTrackingJobStatus } from "$lib/types/inference";

function status(jobId: string, state: VideoTrackingJobStatus["status"]): VideoTrackingJobStatus {
  return { job_id: jobId, status: state, detail: null, data: null };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const immediateSleep = () => Promise.resolve();

describe("createTrackingJobRunner", () => {
  it("polls until the job reaches a terminal status", async () => {
    const changes: (ActiveTrackingJob | null)[] = [];
    const runner = createTrackingJobRunner({
      sleep: immediateSleep,
      onActiveChange: (active) => changes.push(active),
    });
    const getStatus = vi
      .fn<(jobId: string) => Promise<VideoTrackingJobStatus>>()
      .mockResolvedValueOnce(status("job-1", "running"))
      .mockResolvedValueOnce(status("job-1", "completed"));

    const result = await runner.run({
      requestId: "r1",
      kind: "detection",
      viewName: "camera",
      submit: () => Promise.resolve(status("job-1", "running")),
      getStatus,
      cancel: vi.fn(),
    });

    expect(result?.status).toBe("completed");
    expect(getStatus).toHaveBeenCalledTimes(2);
    expect(runner.active).toBeNull();
    expect(changes.map((change) => change?.jobId ?? null)).toEqual([null, "job-1", null]);
  });

  it("returns a terminal submission without polling", async () => {
    const runner = createTrackingJobRunner({ sleep: immediateSleep });
    const getStatus = vi.fn();

    const result = await runner.run({
      requestId: "r1",
      kind: "detection",
      viewName: "camera",
      submit: () => Promise.resolve(status("job-1", "failed")),
      getStatus,
      cancel: vi.fn(),
    });

    expect(result?.status).toBe("failed");
    expect(getStatus).not.toHaveBeenCalled();
    expect(runner.active).toBeNull();
  });

  it("cancels a run superseded while its submission was in flight", async () => {
    const runner = createTrackingJobRunner({ sleep: immediateSleep });
    const firstSubmission = deferred<VideoTrackingJobStatus>();
    const cancelFirst = vi.fn().mockResolvedValue(undefined);

    const first = runner.run({
      requestId: "r1",
      kind: "detection",
      viewName: "camera",
      submit: () => firstSubmission.promise,
      getStatus: vi.fn(),
      cancel: cancelFirst,
    });
    const second = await runner.run({
      requestId: "r2",
      kind: "detection",
      viewName: "camera",
      submit: () => Promise.resolve(status("job-2", "completed")),
      getStatus: vi.fn(),
      cancel: vi.fn(),
    });
    firstSubmission.resolve(status("job-1", "running"));

    expect(second?.job_id).toBe("job-2");
    expect(await first).toBeNull();
    expect(cancelFirst).toHaveBeenCalledWith("job-1");
    expect(runner.active).toBeNull();
  });

  it("cancels the active job on request and resolves the run to null", async () => {
    const sleeping = deferred<void>();
    const runner = createTrackingJobRunner({ sleep: () => sleeping.promise });
    const cancel = vi.fn().mockResolvedValue(undefined);
    const getStatus = vi.fn();

    const run = runner.run({
      requestId: "r1",
      kind: "detection",
      viewName: "camera",
      submit: () => Promise.resolve(status("job-1", "running")),
      getStatus,
      cancel,
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(runner.active?.jobId).toBe("job-1");

    await runner.cancelActive();
    sleeping.resolve();

    expect(await run).toBeNull();
    expect(cancel).toHaveBeenCalledWith("job-1");
    expect(getStatus).not.toHaveBeenCalled();
    expect(runner.active).toBeNull();
  });

  it("clears the active job when the submission throws", async () => {
    const runner = createTrackingJobRunner({ sleep: immediateSleep });

    await expect(
      runner.run({
        requestId: "r1",
        kind: "detection",
        viewName: "camera",
        submit: () => Promise.reject(new Error("boom")),
        getStatus: vi.fn(),
        cancel: vi.fn(),
      }),
    ).rejects.toThrow("boom");
    expect(runner.active).toBeNull();
  });
});
