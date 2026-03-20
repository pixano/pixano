import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import { segmentImage } from "../inferenceApi";

const requestPayload = {
  model: "sam2-image",
  provider_name: "pixano-inference@127.0.0.1:7463",
  dataset_id: "dataset-1",
  view_id: "view-1",
} as const;

describe("segmentImage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns the parsed segmentation result on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          data: {
            masks: [[{ size: [8, 8], counts: "abc" }]],
            scores: { values: [0.9], shape: [1, 1] },
          },
          timestamp: "2026-03-20T10:00:00",
          processing_time: 0.12,
          metadata: {},
          id: "seg-1",
          status: "SUCCESS",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(segmentImage(requestPayload)).resolves.toMatchObject({
      id: "seg-1",
      status: "SUCCESS",
    });
  });

  it("throws ApiError and preserves backend detail on failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Inference server unavailable" }), {
        status: 503,
        statusText: "Service Unavailable",
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      await segmentImage(requestPayload);
      throw new Error("Expected segmentImage to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({
        name: "ApiError",
        status: 503,
        body: JSON.stringify({ detail: "Inference server unavailable" }),
      });
    }
  });
});
