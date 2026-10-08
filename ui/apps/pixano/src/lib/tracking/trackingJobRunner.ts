/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { VideoTrackingJobStatus } from "$lib/types/inference";

/** One tracking job as the workspace drives it: submitted, then polled until a terminal status. */
export interface TrackingJobRun {
  readonly requestId: string;
  readonly kind: string;
  readonly viewName: string;
  readonly submit: () => Promise<VideoTrackingJobStatus | null>;
  readonly getStatus: (jobId: string) => Promise<VideoTrackingJobStatus>;
  readonly cancel: (jobId: string) => Promise<unknown>;
}

export interface ActiveTrackingJob {
  readonly requestId: string;
  readonly jobId: string | null;
  readonly kind: string;
  readonly viewName: string;
}

export interface TrackingJobRunnerOptions {
  pollMs?: number;
  sleep?: (ms: number) => Promise<void>;
  onActiveChange?: (active: ActiveTrackingJob | null) => void;
}

export interface TrackingJobRunner {
  readonly active: ActiveTrackingJob | null;
  run(job: TrackingJobRun): Promise<VideoTrackingJobStatus | null>;
  cancelActive(): Promise<void>;
}

const TERMINAL_STATES: ReadonlySet<string> = new Set(["completed", "failed", "canceled"]);
const DEFAULT_POLL_MS = 500;
const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Runs at most one tracking job at a time. Starting a run cancels the previous one; a run that
 * was superseded while its submission was in flight cancels its own job and resolves to null, so
 * a late result never reaches a caller that moved on.
 */
export function createTrackingJobRunner(options: TrackingJobRunnerOptions = {}): TrackingJobRunner {
  const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
  const sleep = options.sleep ?? defaultSleep;
  let active: ActiveTrackingJob | null = null;
  let cancelActiveJob: ((jobId: string) => Promise<unknown>) | null = null;

  function setActive(
    next: ActiveTrackingJob | null,
    cancel: ((jobId: string) => Promise<unknown>) | null,
  ): void {
    active = next;
    cancelActiveJob = cancel;
    options.onActiveChange?.(active);
  }

  function isCurrent(requestId: string, jobId: string | null): boolean {
    return active?.requestId === requestId && active?.jobId === jobId;
  }

  async function cancelActive(): Promise<void> {
    const job = active;
    const cancel = cancelActiveJob;
    if (!job) return;

    setActive(null, null);
    if (!job.jobId || !cancel) return;

    try {
      await cancel(job.jobId);
    } catch (error) {
      console.warn("Failed to cancel tracking job", error);
    }
  }

  async function run(job: TrackingJobRun): Promise<VideoTrackingJobStatus | null> {
    await cancelActive();
    setActive(
      { requestId: job.requestId, jobId: null, kind: job.kind, viewName: job.viewName },
      job.cancel,
    );

    try {
      const submitted = await job.submit();
      if (!submitted) {
        if (active?.requestId === job.requestId) setActive(null, null);
        return null;
      }

      if (active?.requestId !== job.requestId) {
        try {
          await job.cancel(submitted.job_id);
        } catch (error) {
          console.warn("Failed to cancel stale tracking job", error);
        }
        return null;
      }

      setActive(
        {
          requestId: job.requestId,
          jobId: submitted.job_id,
          kind: job.kind,
          viewName: job.viewName,
        },
        job.cancel,
      );

      if (TERMINAL_STATES.has(submitted.status)) {
        if (active?.requestId === job.requestId) setActive(null, null);
        return submitted;
      }

      while (isCurrent(job.requestId, submitted.job_id)) {
        await sleep(pollMs);
        if (!isCurrent(job.requestId, submitted.job_id)) return null;

        const polled = await job.getStatus(submitted.job_id);
        if (!isCurrent(job.requestId, submitted.job_id)) return null;

        if (polled.status === "queued" || polled.status === "running") continue;

        setActive(null, null);
        return polled;
      }

      return null;
    } catch (error) {
      if (active?.requestId === job.requestId) setActive(null, null);
      throw error;
    }
  }

  return {
    get active() {
      return active;
    },
    run,
    cancelActive,
  };
}
