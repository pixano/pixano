/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { computeEmbeddings, searchRecords } from "../search";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

function requestBody(): Record<string, unknown> {
  const init = fetchMock.mock.calls[0][1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

describe("searchRecords", () => {
  it("sends a text query with filters and adapts the ranked items to a browser view", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        items: [
          { id: "r5", _distance: 0.0 },
          { id: "r1", _distance: 0.3 },
        ],
        total: 2,
        model: "clip",
        mode: "text",
        k: 50,
      }),
    );

    const browser = await searchRecords("ds", {
      text: "a red car",
      k: 50,
      filters: ["split:eq:train"],
      model: "clip",
    });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/datasets/ds/records/search");
    const body = requestBody();
    expect(body).toMatchObject({
      text: "a red car",
      k: 50,
      filter: ["split:eq:train"],
      model: "clip",
    });
    // Ranked order is preserved (no client re-sort).
    expect(browser.table_data.rows.map((r) => r.id)).toEqual(["r5", "r1"]);
    expect(browser.pagination.total_size).toBe(2);
  });

  it("sends similar_to for find-similar", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [{ id: "r7" }], total: 1, model: "clip", mode: "similar", k: 20 }),
    );
    await searchRecords("ds", { similarTo: "r7", k: 20 });
    expect(requestBody()).toMatchObject({ similar_to: "r7", k: 20 });
  });
});

describe("computeEmbeddings", () => {
  it("posts the model and returns the job id", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ job_id: "job-1" }));
    const jobId = await computeEmbeddings("ds", "clip");
    expect(jobId).toBe("job-1");
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/datasets/ds/embeddings/compute");
    expect(requestBody()).toEqual({ model: "clip", force: false });
  });

  it("passes force for repair / model-switch recomputes", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ job_id: "job-2" }));
    await computeEmbeddings("ds", "clip", true);
    expect(requestBody()).toEqual({ model: "clip", force: true });
  });
});
