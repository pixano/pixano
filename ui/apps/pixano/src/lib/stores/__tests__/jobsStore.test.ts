/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "$lib/api/apiClient";
import type { Job } from "$lib/api/jobsApi";

/** A stand-in for the browser's EventSource, driven by the test. */
class FakeStream {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  #listeners = new Map<string, (message: MessageEvent) => void>();

  addEventListener(type: string, listener: (message: MessageEvent) => void): void {
    this.#listeners.set(type, listener);
  }

  emit(type: string, data: unknown): void {
    this.#listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  close(): void {
    this.closed = true;
  }
}

const api = vi.hoisted(() => ({
  listJobs: vi.fn(),
  listJobKinds: vi.fn(),
  probeJobKinds: vi.fn(),
  openJobStream: vi.fn(),
  submitJob: vi.fn(),
  listInferenceModels: vi.fn(),
}));

// Mocked as it is, so that it outlives `vi.resetModules()` as mocked modules do: the jobs module
// below, mocked and so loaded once, tells refusals apart by this ApiError class, and the tests
// build theirs from the same one.
vi.mock("$lib/api/apiClient", async (importOriginal) => await importOriginal());

vi.mock("$lib/api/inferenceApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("$lib/api/inferenceApi")>()),
  listInferenceModels: api.listInferenceModels,
}));

vi.mock("$lib/api/jobsApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("$lib/api/jobsApi")>()),
  listJobs: api.listJobs,
  listJobKinds: api.listJobKinds,
  probeJobKinds: api.probeJobKinds,
  openJobStream: api.openJobStream,
  submitJob: api.submitJob,
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
    finalizing: false,
    ...overrides,
  };
}

type Store = (typeof import("../jobsStore.svelte"))["jobsStore"];

/** A store of its own, in a browser that has EventSource, and the stream it would open. */
async function freshStore(): Promise<{ store: Store; stream: FakeStream }> {
  vi.resetModules();
  const stream = new FakeStream();
  api.openJobStream.mockReturnValue(stream);
  vi.stubGlobal("EventSource", FakeStream);
  const { jobsStore } = await import("../jobsStore.svelte");
  return { store: jobsStore, stream };
}

async function startedStore(): Promise<{ store: Store; stream: FakeStream }> {
  const started = await freshStore();
  await started.store.start();
  return started;
}

/** A kind whose `model` parameter names a model served for `task`. */
function kindWithModel(name: string, task: string) {
  return {
    name,
    params_schema: { properties: { model: { type: "string", "x-pixano-model-task": task } } },
  };
}

/** A kind the worker runs, whose model the inference serves for embeddings. */
const EMBEDDINGS_KIND = kindWithModel("embeddings", "embedding");

beforeEach(() => {
  api.listJobs.mockReset().mockResolvedValue([job()]);
  api.listJobKinds.mockReset().mockResolvedValue([]);
  api.probeJobKinds.mockReset().mockResolvedValue([]);
  api.openJobStream.mockReset();
  api.submitJob.mockReset();
  api.listInferenceModels.mockReset().mockResolvedValue([]);
});

/** What the server answers on an installation without a PostgreSQL database configured. */
const NO_QUEUE_REASON =
  "no job queue is configured — set PIXANO_DATABASE_URL and start pixano-worker";

/** A refusal of the jobs endpoints, with the body the server sent. */
function refusal(status: number, body: string): ApiError {
  return new ApiError(`failed with ${status}`, status, body);
}

/** The refusal the jobs endpoints send when the installation has no job queue. */
function queueUnavailable(reason = NO_QUEUE_REASON): ApiError {
  return refusal(503, JSON.stringify({ detail: reason }));
}

/** Make the lists a panel reads on opening answer that there is no job queue. */
function refuseListsForWantOfAQueue(): void {
  api.listJobs.mockRejectedValue(queueUnavailable());
  api.listJobKinds.mockRejectedValue(queueUnavailable());
}

describe("jobsStore on an installation without a job queue", () => {
  it("says why in the server's words, and offers nothing to run or follow", async () => {
    const { store } = await freshStore();
    refuseListsForWantOfAQueue();

    await store.start();

    expect(store.unavailable).toBe(NO_QUEUE_REASON);
    expect(store.error).toBeNull();
    expect(store.runnable).toBe(false);
    expect(store.loading).toBe(false);
    // The stream would be refused too, and nothing would ever say it reconnected.
    expect(api.openJobStream).not.toHaveBeenCalled();
    expect(api.listInferenceModels).not.toHaveBeenCalled();
  });

  it("drops the kinds of an earlier opening, so no form offers a Run that would fail", async () => {
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);
    const { store } = await startedStore();
    store.stop();
    refuseListsForWantOfAQueue();

    await store.start();

    expect(store.runnable).toBe(false);
    expect(store.jobs).toEqual([]);
  });

  it("finds the queue again when checked once it is set up, and follows from then on", async () => {
    const { store, stream } = await freshStore();
    refuseListsForWantOfAQueue();
    await store.start();
    api.listJobs.mockResolvedValue([job()]);
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);

    await store.start();
    stream.onopen?.();

    expect(store.unavailable).toBeNull();
    expect(store.runnable).toBe(true);
    expect(api.openJobStream).toHaveBeenCalledTimes(1);
    expect(store.live).toBe(true);
  });

  it("stops following when a Run finds the queue gone", async () => {
    // The database went down while the panel was open: the form would only fail again.
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);
    const { store, stream } = await startedStore();
    stream.onopen?.();
    const unreachable = "the job queue is unreachable: connection refused";
    api.submitJob.mockRejectedValue(queueUnavailable(unreachable));

    const accepted = await store.submit("embeddings", "ds", {});

    expect(accepted).toBe(false);
    expect(store.unavailable).toBe(unreachable);
    expect(store.runnable).toBe(false);
    expect(store.live).toBe(false);
    expect(stream.closed).toBe(true);
  });

  it("keeps any other failure an error line, and still follows", async () => {
    const { store } = await freshStore();
    api.listJobs.mockRejectedValue(refusal(500, "boom"));

    await store.start();

    expect(store.unavailable).toBeNull();
    expect(store.error).toBe("failed with 500");
    expect(api.openJobStream).toHaveBeenCalledTimes(1);
  });

  it("takes a 503 without the server's reason for an error, not for a missing queue", async () => {
    // A proxy in front of a server that is down answers 503 too, with a page of its own.
    const { store } = await freshStore();
    api.listJobs.mockRejectedValue(refusal(503, "<html>Service Unavailable</html>"));

    await store.start();

    expect(store.unavailable).toBeNull();
    expect(store.error).toBe("failed with 503");
  });
});

describe("jobsStore asked, outside the panel, whether the embeddings job can run", () => {
  // The explorer asks, to offer its own embeddings computation only where that job cannot run.
  it("says it can when a worker declared it, and follows nothing", async () => {
    api.probeJobKinds.mockResolvedValue([kindWithModel("embeddings", "embedding")]);
    const { store } = await freshStore();

    await store.probe();

    expect(store.offersEmbeddingsJob).toBe(true);
    expect(store.unavailable).toBeNull();
    expect(api.listJobs).not.toHaveBeenCalled();
    expect(api.openJobStream).not.toHaveBeenCalled();
  });

  it("says it cannot on a queue no worker declared it on", async () => {
    // A schema installed by hand, or workers running other kinds only: a pointer to the Jobs
    // panel would lead to a form that cannot compute embeddings.
    api.probeJobKinds.mockResolvedValue([]);
    const { store } = await freshStore();
    await store.probe();
    expect(store.offersEmbeddingsJob).toBe(false);

    api.probeJobKinds.mockResolvedValue([kindWithModel("detection", "detection")]);
    await store.probe();
    expect(store.offersEmbeddingsJob).toBe(false);
    expect(store.unavailable).toBeNull();
  });

  it("says it cannot, and why, when the server says the queue is missing", async () => {
    api.probeJobKinds.mockRejectedValue(queueUnavailable());
    const { store } = await freshStore();

    await store.probe();

    expect(store.offersEmbeddingsJob).toBe(false);
    expect(store.unavailable).toBe(NO_QUEUE_REASON);
  });

  it("says neither when the answer is about something else", async () => {
    api.probeJobKinds.mockRejectedValue(refusal(500, "boom"));
    const { store } = await freshStore();

    await store.probe();

    expect(store.offersEmbeddingsJob).toBe(false);
    expect(store.unavailable).toBeNull();
  });

  it("follows what the panel finds out since", async () => {
    // Opened on an installation whose database then went down: the explorer must offer its own
    // computation again, since no job can run.
    api.probeJobKinds.mockResolvedValue([kindWithModel("embeddings", "embedding")]);
    api.listJobKinds.mockResolvedValue([kindWithModel("embeddings", "embedding")]);
    const { store } = await freshStore();
    await store.probe();
    await store.start();
    api.submitJob.mockRejectedValue(queueUnavailable("the job queue is unreachable"));

    await store.submit("embeddings", "ds", {});

    expect(store.offersEmbeddingsJob).toBe(false);
  });

  it("leaves the answer of a panel open meanwhile, which follows what it heard", async () => {
    let answerProbe: (kinds: unknown[]) => void = () => {};
    api.probeJobKinds.mockReturnValueOnce(new Promise((resolve) => (answerProbe = resolve)));
    const { store } = await freshStore();
    const probing = store.probe();
    refuseListsForWantOfAQueue();
    await store.start();

    answerProbe([kindWithModel("embeddings", "embedding")]);
    await probing;

    expect(store.unavailable).toBe(NO_QUEUE_REASON);
    expect(store.offersEmbeddingsJob).toBe(false);
    expect(store.runnable).toBe(false);
  });
});

describe("jobsStore closed while its lists load", () => {
  it("opens no stream and asks for no models once stopped before the lists arrive", async () => {
    // Escape right after opening the panel: stop() runs while start() still awaits.
    let finishListing: (jobs: Job[]) => void = () => {};
    api.listJobs.mockReturnValue(new Promise<Job[]>((resolve) => (finishListing = resolve)));
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);
    const { store } = await freshStore();

    const starting = store.start();
    store.stop();
    finishListing([job()]);
    await starting;

    expect(api.openJobStream).not.toHaveBeenCalled();
    expect(api.listInferenceModels).not.toHaveBeenCalled();
    expect(store.live).toBe(false);
  });

  it("follows for the panel opened again before the first lists arrived", async () => {
    // Closing a panel must not stop the next one from following. The first start, landing
    // last, leaves the following to the second: no second stream, no second question about
    // the models served.
    let finishFirstListing: (jobs: Job[]) => void = () => {};
    api.listJobs.mockReturnValueOnce(
      new Promise<Job[]>((resolve) => (finishFirstListing = resolve)),
    );
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);
    const { store, stream } = await freshStore();

    const closed = store.start();
    store.stop();
    await store.start();
    finishFirstListing([job()]);
    await closed;
    stream.onopen?.();

    expect(api.openJobStream).toHaveBeenCalledTimes(1);
    expect(api.listInferenceModels).toHaveBeenCalledTimes(1);
    expect(store.live).toBe(true);
  });
  it("keeps the lists of the panel opened again when the first answer lands last", async () => {
    // Open, Escape, open again, and the first panel's lists are the slowest: they must not
    // replace the newer ones the second opening already shows.
    let finishFirstListing: (jobs: Job[]) => void = () => {};
    api.listJobs
      .mockReturnValueOnce(new Promise<Job[]>((resolve) => (finishFirstListing = resolve)))
      .mockResolvedValueOnce([job({ id: "newer" })]);
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);
    const { store } = await freshStore();

    const closed = store.start();
    store.stop();
    await store.start();
    finishFirstListing([job({ id: "older" })]);
    await closed;

    expect(store.jobs.map((listed) => listed.id)).toEqual(["newer"]);
    expect(store.loading).toBe(false);
  });
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
    // Only the tab that clicked knew; every other kept "running".
    const { store, stream } = await startedStore();

    stream.emit("state", { job_id: "j1", state: "running", cancel_requested: true });

    expect(store.jobs[0].cancel_requested).toBe(true);
    expect(store.jobs[0].state).toBe("running");
  });
});

describe("jobsStore hearing a job finalize", () => {
  it("shows the job finalizing from the event alone, then done", async () => {
    const { store, stream } = await startedStore();
    const { stateLabelOf } = await import("../jobsStore.svelte");

    stream.emit("state", { job_id: "j1", state: "running", finalizing: true });

    expect(stateLabelOf(store.jobs[0])).toBe("finalizing");

    stream.emit("state", {
      job_id: "j1",
      state: "done",
      produced: 400,
      skipped: 0,
      quarantined: 0,
    });

    expect(stateLabelOf(store.jobs[0])).toBe("done");
  });
});

describe("jobsStore hearing a job leave its closing step", () => {
  it("drops the finalizing flag at the next state event that does not carry it", async () => {
    const { store, stream } = await startedStore();
    const { stateLabelOf } = await import("../jobsStore.svelte");
    stream.emit("state", { job_id: "j1", state: "running", finalizing: true });

    stream.emit("state", { job_id: "j1", state: "running", cancel_requested: true });
    stream.emit("state", { job_id: "j1", state: "cancelled", cancel_requested: true });
    stream.emit("state", { job_id: "j1", state: "pending", cancel_requested: false });

    expect(store.jobs[0].finalizing).toBe(false);
    expect(stateLabelOf(store.jobs[0])).toBe("pending");
  });

  it("keeps it through a progress event, which carries no state", async () => {
    const { store, stream } = await startedStore();
    stream.emit("state", { job_id: "j1", state: "running", finalizing: true });

    stream.emit("progress", { job_id: "j1", done_tasks: 400, total_tasks: 400 });

    expect(store.jobs[0].finalizing).toBe(true);
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

describe("jobsStore asking which models are served", () => {
  it("asks once per task the kinds need, and keeps the names", async () => {
    api.listJobKinds.mockResolvedValue([
      kindWithModel("detection", "detection"),
      kindWithModel("embeddings", "embedding"),
    ]);
    api.listInferenceModels.mockImplementation((task: string) =>
      Promise.resolve([
        { name: task === "detection" ? "yolo26s" : "clip", task, provider_name: "p" },
      ]),
    );

    const { store } = await startedStore();

    expect(
      api.listInferenceModels.mock.calls.map((call: unknown[]) => call[0] as string).sort(),
    ).toEqual(["detection", "embedding"]);
    expect(store.servedModels).toEqual({ detection: ["yolo26s"], embedding: ["clip"] });
  });

  it("leaves out a task the inference cannot answer for, and still loads the others", async () => {
    api.listJobKinds.mockResolvedValue([
      kindWithModel("detection", "detection"),
      kindWithModel("embeddings", "embedding"),
    ]);
    api.listInferenceModels.mockImplementation((task: string) =>
      task === "detection"
        ? Promise.reject(new Error("unsupported task"))
        : Promise.resolve([{ name: "clip", task, provider_name: "p" }]),
    );

    const { store } = await startedStore();

    expect(store.servedModels).toEqual({ embedding: ["clip"] });
  });
});
