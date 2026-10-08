/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import {
  cancelTrackingJob,
  getTrackingJob,
  segmentImage,
  submitTrackingJob,
  trackVideo,
} from "../inferenceApi";

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

describe("trackVideo", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("throws ApiError and preserves backend detail on failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail:
            "Model 'sam2-video' is a video_mask_generation model; use /inference/video_mask_generation",
        }),
        {
          status: 400,
          statusText: "Bad Request",
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(
      trackVideo({
        model: "sam2-video",
        provider_name: "pixano-inference@127.0.0.1:7463",
        dataset_id: "dataset-1",
        record_id: "record-1",
        view_name: "camera",
        start_frame_index: 0,
        frame_count: 1,
        objects_ids: [1],
        prompt_frame_indexes: [0],
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      body: JSON.stringify({
        detail:
          "Model 'sam2-video' is a video_mask_generation model; use /inference/video_mask_generation",
      }),
    });
  });
});

describe("tracking job APIs", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("submits tracking jobs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          job_id: "tracking-job-1",
          status: "running",
          detail: null,
          data: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(
      submitTrackingJob({
        model: "sam2-video",
        provider_name: "pixano-inference@127.0.0.1:7463",
        dataset_id: "dataset-1",
        record_id: "record-1",
        view_name: "camera",
        start_frame_index: 0,
        frame_count: 1,
        objects_ids: [1],
        prompt_frame_indexes: [0],
      }),
    ).resolves.toMatchObject({
      job_id: "tracking-job-1",
      status: "running",
    });
  });

  it("submits prompt-free tracking jobs with classes and a detection floor", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ job_id: "tracking-job-2", status: "running", detail: null, data: null }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await submitTrackingJob({
      model: "yolo-bytetrack",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      record_id: "record-1",
      view_name: "camera",
      start_frame_index: 0,
      frame_count: 120,
      objects_ids: [],
      prompt_frame_indexes: [],
      classes: ["person"],
      box_threshold: 0.4,
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/inference/video_mask_generation/jobs");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body).toMatchObject({ objects_ids: [], classes: ["person"], box_threshold: 0.4 });
    expect(body).not.toHaveProperty("keyframes");
  });

  it("polls tracking jobs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          job_id: "tracking-job-1",
          status: "completed",
          data: {
            frames: [
              { frame_index: 0, objects: [{ track_id: 1, mask: { size: [8, 8], counts: "abc" } }] },
            ],
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(getTrackingJob("tracking-job-1")).resolves.toMatchObject({
      job_id: "tracking-job-1",
      status: "completed",
      data: { frames: [{ frame_index: 0, objects: [{ track_id: 1 }] }] },
    });
  });

  it("cancels tracking jobs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          job_id: "tracking-job-1",
          status: "canceled",
          detail: "Tracking job canceled.",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(cancelTrackingJob("tracking-job-1")).resolves.toMatchObject({
      job_id: "tracking-job-1",
      status: "canceled",
    });
  });
});
