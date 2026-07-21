/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  activeJobEntries,
  applyJobUpdate,
  isTerminalJob,
  type ImportJobEntry,
} from "$components/library/import-wizard/wizardUtils";

import { reactiveStore } from "./reactiveStore.svelte";
import { invalidateAll } from "$app/navigation";
import { cancelIoJob, getIoJob } from "$lib/api/ioApi";
import type { IoJobResponse } from "$lib/api/restTypes";

/** Background imports: the jobs run server-side; this tracks and polls them. */
export const importJobsStore = reactiveStore<ImportJobEntry[]>([]);

let pollHandle: ReturnType<typeof setInterval> | null = null;

function ensurePolling() {
  if (pollHandle || typeof window === "undefined") return;
  pollHandle = setInterval(() => {
    void pollActiveJobs();
  }, 2000);
}

function stopPollingIfIdle() {
  if (pollHandle && activeJobEntries(importJobsStore.value).length === 0) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

async function pollActiveJobs() {
  for (const entry of activeJobEntries(importJobsStore.value)) {
    try {
      const job = await getIoJob(entry.jobId);
      const { entries, completedNow } = applyJobUpdate(importJobsStore.value, job);
      importJobsStore.value = entries;
      if (completedNow) await invalidateAll();
    } catch {
      // Transient poll failure (server restart, network): keep the entry, retry next tick.
    }
  }
  stopPollingIfIdle();
}

/** Register a freshly started import; polling begins immediately. */
export function trackImportJob(job: IoJobResponse, dataset: string) {
  if (importJobsStore.value.some((entry) => entry.jobId === job.job_id)) return;
  importJobsStore.value = [
    ...importJobsStore.value,
    { jobId: job.job_id, dataset, job, cancelRequested: false, dismissed: false },
  ];
  ensurePolling();
}

/** Cooperative cancel (takes effect at the job's next commit boundary). */
export async function requestImportJobCancel(jobId: string) {
  const entry = importJobsStore.value.find((candidate) => candidate.jobId === jobId);
  if (!entry || entry.cancelRequested || isTerminalJob(entry.job.status)) return;
  importJobsStore.value = importJobsStore.value.map((candidate) =>
    candidate.jobId === jobId ? { ...candidate, cancelRequested: true } : candidate,
  );
  try {
    await cancelIoJob(jobId);
  } catch {
    importJobsStore.value = importJobsStore.value.map((candidate) =>
      candidate.jobId === jobId ? { ...candidate, cancelRequested: false } : candidate,
    );
  }
}

/** Remove a finished entry from the tray. */
export function dismissImportJob(jobId: string) {
  importJobsStore.value = importJobsStore.value.map((entry) =>
    entry.jobId === jobId ? { ...entry, dismissed: true } : entry,
  );
  stopPollingIfIdle();
}
