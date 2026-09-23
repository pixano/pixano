/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { JSON_HEADERS, requestJson } from "./apiClient";

/** A processing job, as the backend reports it. */
export type Job = {
  id: string;
  kind: string;
  dataset: string;
  state: JobState;
  total_tasks: number;
  /** Tasks attempted so far — what the progress bar shows. */
  done_tasks: number;
  /** Tasks that gave a result. */
  produced: number;
  /** Tasks the kind does not apply to, such as a record without an image. Not a failure. */
  skipped: number;
  /** Tasks that failed, readable one by one from the quarantine. */
  quarantined: number;
  /** Someone asked the job to stop; the chunks in flight are finishing. */
  cancel_requested: boolean;
  /** Why the job failed, when it did — at least a `reason`. Null otherwise. */
  error: Record<string, unknown> | null;
  created_at: string;
};

/** An item a job could not process, and why. */
export type QuarantinedItem = {
  item_id: string;
  reason: string;
  detail: Record<string, unknown> | null;
  created_at: string;
};

export type JobState = "planning" | "pending" | "running" | "done" | "error" | "cancelled";

/** A job state nobody is waiting on any more. */
export const TERMINAL_STATES: readonly JobState[] = ["done", "error", "cancelled"];

export function isTerminal(state: JobState): boolean {
  return TERMINAL_STATES.includes(state);
}

/** A kind a worker declared it can run, with the shape of its parameters. */
export type JobKind = {
  name: string;
  params_schema: JsonSchema;
};

/** The subset of JSON Schema the launch form understands. */
export type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  default?: unknown;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  anyOf?: JsonSchema[];
  items?: JsonSchema;
  /** Set on a parameter that destroys something when set: the form asks before running. */
  "x-pixano-confirm"?: string;
};

/** The dataset a job would run on — the one last opened in the Explorer. */
export type JobTarget = { id: string; name: string };

export type SubmitJobRequest = {
  kind: string;
  dataset_id: string;
  params: Record<string, unknown>;
};

export function listJobs(limit = 50): Promise<Job[]> {
  return requestJson<Job[]>(`/jobs?limit=${limit}`, {}, "listJobs");
}

export function getJob(jobId: string): Promise<Job> {
  return requestJson<Job>(`/jobs/${jobId}`, {}, "getJob");
}

export function listJobKinds(): Promise<JobKind[]> {
  return requestJson<JobKind[]>("/jobs/kinds", {}, "listJobKinds");
}

export function submitJob(request: SubmitJobRequest): Promise<Job> {
  return requestJson<Job>(
    "/jobs",
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(request) },
    "submitJob",
  );
}

export function listJobQuarantine(jobId: string, limit = 100): Promise<QuarantinedItem[]> {
  return requestJson<QuarantinedItem[]>(
    `/jobs/${jobId}/quarantine?limit=${limit}`,
    {},
    "listJobQuarantine",
  );
}

export function cancelJob(jobId: string): Promise<Job> {
  return requestJson<Job>(`/jobs/${jobId}/cancel`, { method: "POST" }, "cancelJob");
}

/** What a job event carries, flattened as the stream sends it. */
export type JobEvent = {
  job_id: string;
  state?: JobState;
  done_tasks?: number;
  total_tasks?: number;
  chunks?: number;
  reason?: string;
  detail?: string;
  produced?: number;
  skipped?: number;
  quarantined?: number;
  cancel_requested?: boolean;
};

/**
 * Open the stream of every job's events.
 *
 * One connection for all jobs, on purpose: browsers allow very few concurrent connections
 * per host, so a stream per running job would starve the rest of the application.
 *
 * The returned EventSource reconnects on its own, but this stream does not catch up on what
 * happened while it was down: resuming from `Last-Event-ID` is only implemented for the stream
 * of a single job. A client that reconnects must reload what it shows.
 */
export function openJobStream(types: string[] = ["state", "progress"]): EventSource {
  return new EventSource(`/jobs/events?types=${types.join(",")}`);
}
