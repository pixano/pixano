/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import JobsPanel from "../JobsPanel.svelte";
import { ApiError } from "$lib/api/apiClient";
import { jobsStore } from "$lib/stores/jobs.svelte";

/** A stream that stays silent: these tests are about what the panel shows before any event. */
class SilentStream {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener(): void {}
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

const NOTICE_TITLE = "Jobs are not available on this installation";
const NO_QUEUE_REASON =
  "no job queue is configured — set PIXANO_DATABASE_URL and start pixano-worker";
const DATASET = { id: "ds", name: "Dataset" };
const EMBEDDINGS_KIND = { name: "embeddings", params_schema: { type: "object", properties: {} } };

/** What the jobs endpoints answer on an installation without a job queue. */
function queueUnavailable(): ApiError {
  return new ApiError(
    "listJobs failed with 503 Service Unavailable",
    503,
    JSON.stringify({ detail: NO_QUEUE_REASON }),
  );
}

beforeEach(() => {
  vi.stubGlobal("EventSource", SilentStream);
  api.openJobStream.mockReset().mockReturnValue(new SilentStream());
  api.listJobs.mockReset().mockRejectedValue(queueUnavailable());
  api.listJobKinds.mockReset().mockRejectedValue(queueUnavailable());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // The store is a module singleton, which the panel only stops when it closes: each test starts
  // from a panel never opened, not from the missing queue the previous one found.
  jobsStore.jobs = [];
  jobsStore.kinds = [];
  jobsStore.error = null;
  jobsStore.unavailable = null;
});

describe("JobsPanel on an installation without a job queue", () => {
  it("says so, and why in the server's words, in place of the form and the list", async () => {
    render(JobsPanel, { props: { dataset: DATASET } });

    await waitFor(() => expect(screen.getByText(NOTICE_TITLE)).toBeTruthy());
    expect(screen.getByText(NO_QUEUE_REASON)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Run" })).toBeNull();
    expect(screen.queryByText(/No worker is running/)).toBeNull();
    expect(screen.queryByText("Reconnecting to the event stream…")).toBeNull();
  });

  it("offers the form once Check again finds the queue set up", async () => {
    render(JobsPanel, { props: { dataset: DATASET } });
    // The button reads "Checking…" while the panel's own check is under way.
    const checkAgain = await screen.findByRole("button", { name: "Check again" });
    api.listJobs.mockResolvedValue([]);
    api.listJobKinds.mockResolvedValue([EMBEDDINGS_KIND]);

    await fireEvent.click(checkAgain);

    await waitFor(() => expect(screen.getByRole("button", { name: "Run" })).toBeTruthy());
    expect(screen.queryByText(NOTICE_TITLE)).toBeNull();
  });
});
