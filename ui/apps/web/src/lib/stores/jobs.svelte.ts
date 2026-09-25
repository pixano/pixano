/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { listInferenceModels } from "$lib/api/inference";
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
import { modelTasks, type ServedModels } from "$lib/components/jobs/schemaForm";

/**
 * The jobs a user can see, kept current by one event stream.
 *
 * Polling is deliberately absent: the backend pushes an event per state change and per
 * finished chunk. The stream reconnects on its own after an outage but does not replay what it
 * missed, so the list is reloaded once on each reconnection — not on a timer, which would add
 * load and still lag.
 */
class JobsStore {
  jobs = $state<Job[]>([]);
  kinds = $state<JobKind[]>([]);
  /** The models the inference serves, by task, for the kinds that run one. */
  servedModels = $state<ServedModels>({});
  loading = $state(false);
  /** What went wrong last, for the panel to show. Null when all is well. */
  error = $state<string | null>(null);
  /** True once the stream is carrying events. */
  live = $state(false);
  /** The quarantine of each job someone asked to see, by job identifier. */
  quarantines = $state<Record<string, QuarantinedItem[]>>({});

  #stream: EventSource | null = null;
  /** The stream failed since it last opened: whatever it opens next, events were missed. */
  #missedEvents = false;
  /** The reload in progress, shared by everyone who asks for one meanwhile. */
  #refreshing: Promise<void> | null = null;

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
    await this.#loadServedModels();
  }

  /**
   * Ask the inference which models it serves for each task the kinds need.
   *
   * A task it cannot answer for is left out: its field is then typed, and the worker, which
   * asks its own inference, refuses a wrong name with the models it does serve.
   */
  async #loadServedModels(): Promise<void> {
    const tasks = modelTasks(this.kinds.map((kind) => kind.params_schema));
    const answers = await Promise.all(tasks.map((task) => servedNames(task)));
    const served: ServedModels = {};
    tasks.forEach((task, index) => {
      if (answers[index].length > 0) served[task] = answers[index];
    });
    this.servedModels = served;
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
      // A job that finished during the outage would otherwise read "running" until the panel is
      // reopened: the global stream has no catch-up. Found in the step 1 code review.
      if (this.#missedEvents) {
        this.#missedEvents = false;
        void this.refresh();
      }
    };
    // EventSource retries on its own, so a drop is not an error to report — only a loss of
    // liveness. Saying "connection lost" on every hiccup would train the user to ignore it.
    stream.onerror = () => {
      this.live = false;
      this.#missedEvents = true;
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
      // A job someone else submitted. Its events keep coming until the reload lands, so the
      // reload is shared rather than started once per event.
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
      cancel_requested: event.cancel_requested ?? current.cancel_requested,
      error: event.reason ? { reason: event.reason, detail: event.detail } : current.error,
    };
  }

  #merge(job: Job): void {
    const index = this.jobs.findIndex((known) => known.id === job.id);
    if (index === -1) this.jobs = [job, ...this.jobs];
    else this.jobs[index] = job;
  }

  /**
   * Reload the list — once, however many callers ask at the same time.
   *
   * Every event of a job this panel has never seen asks for a reload, and a job submitted from
   * elsewhere sends one per finished chunk: without sharing, that was a burst of identical
   * requests, each opening a database connection on the server.
   */
  refresh(): Promise<void> {
    this.#refreshing ??= this.#reload().finally(() => {
      this.#refreshing = null;
    });
    return this.#refreshing;
  }

  async #reload(): Promise<void> {
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
/** The names of the models served for a task; none when the inference cannot say. */
async function servedNames(task: string): Promise<string[]> {
  try {
    return (await listInferenceModels(task)).map((model) => model.name);
  } catch {
    return [];
  }
}

export function progressOf(job: Job): number {
  if (job.total_tasks <= 0) return 0;
  return Math.min(1, job.done_tasks / job.total_tasks);
}

/**
 * The state to show for a job.
 *
 * A cancelled job keeps running for a few seconds while its chunks in flight finish — nothing is
 * interrupted mid-chunk. Showing "running" meanwhile makes the click look lost.
 */
export function stateLabelOf(job: Job): string {
  if (job.cancel_requested && !isTerminal(job.state)) return "cancelling";
  return job.state;
}

/** Why a job failed, in one line — or null when it did not fail. */
export function failureOf(job: Job): string | null {
  if (job.state !== "error") return null;
  const reason = job.error?.reason;
  const detail = job.error?.detail;
  if (typeof reason !== "string" || !reason) return "failed for an unknown reason";
  // The reason says which step failed, the detail says why — a job refused at planning reads
  // "planning failed" and nothing more without it.
  return typeof detail === "string" && detail ? `${reason}: ${detail}` : reason;
}

/**
 * The record a quarantined item belongs to, when the job said so.
 *
 * An item is a medium now — one camera of a record — and its identifier alone does not tell a
 * user which record to open.
 */
export function recordOf(item: QuarantinedItem): string | null {
  const recordId = item.detail?.record_id;
  return typeof recordId === "string" && recordId ? recordId : null;
}

/** Whether a Cancel button makes sense: the job still runs and nobody has asked it to stop. */
export function canCancel(job: Job): boolean {
  return !isTerminal(job.state) && !job.cancel_requested;
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
