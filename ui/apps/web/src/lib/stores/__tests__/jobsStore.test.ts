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
