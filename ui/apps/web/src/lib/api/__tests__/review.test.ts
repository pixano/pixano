/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import { getNextRecordToReview } from "../review";
import { httpReviewGateway } from "$lib/workspace/reviewGateway.js";

function okJson(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getNextRecordToReview", () => {
  it("asks the review endpoint for a status, after a record", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ record_id: "r2", remaining: 3 }));

    const result = await getNextRecordToReview("ds-1", { status: "accepted", after: "r1" });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url.startsWith("/datasets/ds-1/review/next?")).toBe(true);
    const params = new URLSearchParams(url.split("?")[1]);
    expect(params.get("status")).toBe("accepted");
    expect(params.get("after")).toBe("r1");
    expect(result).toEqual({ record_id: "r2", remaining: 3 });
  });

  it("leaves `after` out when there is no record to start after", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ record_id: null, remaining: 0 }));

    await getNextRecordToReview("ds-1", { status: "pending", after: null });

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(new URLSearchParams(url.split("?")[1]).has("after")).toBe(false);
  });

  it("throws an ApiError carrying the server's answer", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('{"detail":"bad status"}', { status: 422, statusText: "Unprocessable" }),
    );

    await expect(getNextRecordToReview("ds-1", { status: "nope" })).rejects.toBeInstanceOf(
      ApiError,
    );
  });
});

describe("httpReviewGateway", () => {
  it("maps the response to the workspace's shape", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ record_id: "r9", remaining: 1 }));

    const next = await httpReviewGateway.nextRecordToReview("ds-1", {
      status: "pending",
      after: "r1",
    });

    expect(next).toEqual({ recordId: "r9", remaining: 1 });
  });
});
