/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getNextRecordToReview } from "../reviewApi";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const answer = (payload: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(payload), { status }));

const requestedUrl = (): string => {
  const [url] = fetchMock.mock.calls[0];
  return typeof url === "string" ? url : url instanceof URL ? url.href : url.url;
};

describe("the next record to review", () => {
  it("asks for the records still to review after the one left", async () => {
    fetchMock.mockReturnValueOnce(answer({ record_id: "record-2", remaining: 3 }));

    const next = await getNextRecordToReview("ds", "record-1");

    expect(requestedUrl()).toBe("/datasets/ds/review/next?status=pending&after=record-1");
    expect(next).toEqual({ record_id: "record-2", remaining: 3 });
  });

  it("asks for the first one when no record is left", async () => {
    fetchMock.mockReturnValueOnce(answer({ record_id: "record-1", remaining: 1 }));

    await getNextRecordToReview("ds");

    expect(requestedUrl()).toBe("/datasets/ds/review/next?status=pending");
  });

  it("reads that none is left", async () => {
    fetchMock.mockReturnValueOnce(answer({ record_id: null, remaining: 0 }));

    expect(await getNextRecordToReview("ds", "record-1")).toEqual({
      record_id: null,
      remaining: 0,
    });
  });

  it("fails when the server does", async () => {
    fetchMock.mockReturnValueOnce(answer({ detail: "Dataset not found" }, 404));

    await expect(getNextRecordToReview("missing")).rejects.toMatchObject({ status: 404 });
  });
});
