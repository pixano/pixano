/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  cancelJob,
  isTerminal,
  listJobKinds,
  listJobQuarantine,
  listJobs,
  openJobStream,
  submitJob,
  type Job,
  type JobEvent,
  type JobKind,
  type QuarantinedItem,
} from "$lib/api/jobs";

/**
 * The jobs a user can see, kept current by one event stream.
 *
 * Polling is deliberately absent: the backend pushes an event per state change and per
 * finished chunk, and the stream reconnects on its own after an outage, resuming from the
 * last identifier it received. Refreshing the list on a timer would add load and still lag.
 */
class JobsStore {
  jobs = $state<Job[]>([]);
  kinds = $state<JobKind[]>([]);
  loading = $state(false);
  /** What went wrong last, for the panel to show. Null when all is well. */
  error = $state<string | null>(null);
  /** True once the stream is carrying events. */
  live = $state(false);
  /** The quarantine of each job someone asked to see, by job identifier. */
  quarantines = $state<Record<string, QuarantinedItem[]>>({});

  #stream: EventSource | null = null;

  /** Load the list and the runnable kinds, then follow along. */
  async start(): Promise<void> {
    this.loading = true;
    try {
      const [jobs, kinds] = await Promise.all([listJobs(), listJobKinds()]);
      this.jobs = jobs;
      this.kinds = kinds;
      this.error = null;
    } catch (cause) {
      this.error = describe(cause);
    } finally {
      this.loading = false;
    }
    this.#follow();
  }

  /** Stop following. Safe to call twice. */
  stop(): void {
    this.#stream?.close();
    this.#stream = null;
    this.live = false;
  }

  /** Whether anything can be launched at all — no worker means no kinds. */
  get runnable(): boolean {
    return this.kinds.length > 0;
  }

  async submit(kind: string, datasetId: string, params: Record<string, unknown>): Promise<boolean> {
    try {
      const job = await submitJob({ kind, dataset_id: datasetId, params });
      this.jobs = [job, ...this.jobs];
      this.error = null;
      return true;
    } catch (cause) {
      this.error = describe(cause);
      return false;
    }
  }

  /** Fetch the items a job set aside. Read on demand: most jobs have none, and nobody looks. */
  async loadQuarantine(jobId: string): Promise<void> {
    try {
      this.quarantines[jobId] = await listJobQuarantine(jobId);
      this.error = null;
    } catch (cause) {
      this.error = describe(cause);
    }
  }

  async cancel(jobId: string): Promise<void> {
    try {
      this.#merge(await cancelJob(jobId));
      this.error = null;
    } catch (cause) {
      this.error = describe(cause);
    }
  }

  #follow(): void {
    if (this.#stream || typeof EventSource === "undefined") return;
    const stream = openJobStream();
    this.#stream = stream;

    stream.onopen = () => {
      this.live = true;
    };
    // EventSource retries on its own, so a drop is not an error to report — only a loss of
    // liveness. Saying "connection lost" on every hiccup would train the user to ignore it.
    stream.onerror = () => {
      this.live = false;
    };
    stream.addEventListener("state", (event) => this.#apply(event));
    stream.addEventListener("progress", (event) => this.#apply(event));
  }

  #apply(message: MessageEvent): void {
    let event: JobEvent;
    try {
      event = JSON.parse(message.data) as JobEvent;
    } catch {
      return;
    }
    const index = this.jobs.findIndex((job) => job.id === event.job_id);
    if (index === -1) {
      // A job someone else submitted. Fetching the whole list is heavy-handed, but it only
      // happens on a job we have never seen, which is rare and never in a loop.
      void this.refresh();
      return;
    }
    const current = this.jobs[index];
    this.jobs[index] = {
      ...current,
      state: event.state ?? current.state,
      done_tasks: event.done_tasks ?? current.done_tasks,
      total_tasks: event.total_tasks ?? current.total_tasks,
      produced: event.produced ?? current.produced,
      skipped: event.skipped ?? current.skipped,
      quarantined: event.quarantined ?? current.quarantined,
    };
  }

  #merge(job: Job): void {
    const index = this.jobs.findIndex((known) => known.id === job.id);
    if (index === -1) this.jobs = [job, ...this.jobs];
    else this.jobs[index] = job;
  }

  async refresh(): Promise<void> {
    try {
      this.jobs = await listJobs();
      this.error = null;
    } catch (cause) {
      this.error = describe(cause);
    }
  }
}

/** Turn a thrown value into something worth showing a user. */
function describe(cause: unknown): string {
  if (cause instanceof Error) return cause.message;
  return String(cause);
}

/** How far along a job is, between 0 and 1. Zero total means nothing to show yet. */
export function progressOf(job: Job): number {
  if (job.total_tasks <= 0) return 0;
  return Math.min(1, job.done_tasks / job.total_tasks);
}

/**
 * What a finished job produced, in words — or null while it runs.
 *
 * Progress alone says how much was attempted: a job over a lidar dataset reaches
 * 26 766 / 26 766 having embedded 404 images. This is the line that says so.
 */
export function outcomeOf(job: Job): string | null {
  if (!isTerminal(job.state)) return null;
  const parts = [`${job.produced} produced`];
  if (job.skipped > 0) parts.push(`${job.skipped} skipped`);
  if (job.quarantined > 0) parts.push(`${job.quarantined} quarantined`);
  return parts.join(" · ");
}

export { isTerminal };
export const jobsStore = new JobsStore();
