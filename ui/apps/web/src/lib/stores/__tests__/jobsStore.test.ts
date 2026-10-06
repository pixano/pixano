/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Job } from "$lib/api/jobs";

/** A stand-in for the browser's EventSource, driven by the test. */
class FakeStream {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  #listeners = new Map<string, (message: MessageEvent) => void>();

  addEventListener(type: string, listener: (message: MessageEvent) => void): void {
    this.#listeners.set(type, listener);
  }

  emit(type: string, data: unknown): void {
    this.#listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  close(): void {}
}

const api = vi.hoisted(() => ({
  listJobs: vi.fn(),
  listJobKinds: vi.fn(),
  openJobStream: vi.fn(),
}));

vi.mock("$lib/api/jobs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("$lib/api/jobs")>()),
  listJobs: api.listJobs,
  listJobKinds: api.listJobKinds,
  openJobStream: api.openJobStream,
}));

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "j1",
    kind: "embeddings",
    dataset: "ds",
    state: "running",
    total_tasks: 400,
    done_tasks: 40,
    produced: 0,
    skipped: 0,
    quarantined: 0,
    cancel_requested: false,
    error: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

async function startedStore(): Promise<{
  store: (typeof import("../jobs.svelte"))["jobsStore"];
  stream: FakeStream;
}> {
  vi.resetModules();
  const stream = new FakeStream();
  api.openJobStream.mockReturnValue(stream);
  vi.stubGlobal("EventSource", FakeStream);
  const { jobsStore } = await import("../jobs.svelte");
  await jobsStore.start();
  return { store: jobsStore, stream };
}

beforeEach(() => {
  api.listJobs.mockReset().mockResolvedValue([job()]);
  api.listJobKinds.mockReset().mockResolvedValue([]);
  api.openJobStream.mockReset();
});

describe("jobsStore after a stream outage", () => {
  it("does not reload when the stream first opens", async () => {
    const { stream } = await startedStore();

    stream.onopen?.();

    expect(api.listJobs).toHaveBeenCalledTimes(1);
  });

  it("reloads the list when the stream comes back, since it replays nothing", async () => {
    // A job that ended during the outage would otherwise read "running" for good.
    const { store, stream } = await startedStore();
    stream.onopen?.();
    api.listJobs.mockResolvedValue([job({ state: "done", done_tasks: 400 })]);

    stream.onerror?.();
    stream.onopen?.();
    await vi.waitFor(() => expect(store.jobs[0].state).toBe("done"));

    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });
});

describe("jobsStore facing a job it has never seen", () => {
  it("reloads once for a burst of its events, not once per event", async () => {
    const { store, stream } = await startedStore();
    let finishReload: (jobs: Job[]) => void = () => {};
    api.listJobs.mockReturnValue(new Promise<Job[]>((resolve) => (finishReload = resolve)));

    for (let done = 8; done <= 160; done += 8) {
      stream.emit("progress", { job_id: "someone-else", done_tasks: done, total_tasks: 400 });
    }
    finishReload([job(), job({ id: "someone-else" })]);
    await vi.waitFor(() => expect(store.jobs).toHaveLength(2));

    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("can reload again once the previous reload has landed", async () => {
    const { store } = await startedStore();

    await store.refresh();
    await store.refresh();

    expect(api.listJobs).toHaveBeenCalledTimes(3);
  });
});

describe("jobsStore hearing a cancellation made elsewhere", () => {
  it("shows the job as cancelling from the event alone", async () => {
    // Independent review, D3: only the tab that clicked knew; every other kept "running".
    const { store, stream } = await startedStore();

    stream.emit("state", { job_id: "j1", state: "running", cancel_requested: true });

    expect(store.jobs[0].cancel_requested).toBe(true);
    expect(store.jobs[0].state).toBe("running");
  });
});

describe("jobsStore hearing a failure", () => {
  it("keeps the reason the state event carries", async () => {
    const { store, stream } = await startedStore();

    stream.emit("state", {
      job_id: "j1",
      state: "error",
      reason: "planning failed",
      detail: "boom",
    });

    expect(store.jobs[0].error).toEqual({ reason: "planning failed", detail: "boom" });
  });
});
