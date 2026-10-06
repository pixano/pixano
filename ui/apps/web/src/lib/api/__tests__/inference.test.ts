/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../apiClient";
import { generateImageMask, listInferenceModels, MASK_GENERATION_TASK } from "../inference";

function okJson(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(body),
  } as Response;
}

function errResponse(status: number, statusText: string): Response {
  return {
    ok: false,
    status,
    statusText,
    // `requestJson` reads the body as text to build the error message.
    text: () => Promise.resolve("provider unavailable"),
    json: () => Promise.resolve({}),
  } as Response;
}

/** Read the JSON body the client sent, without repeating the cast. */
function sentBody(): Record<string, unknown> {
  const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listInferenceModels", () => {
  it("returns an empty list when no provider is connected", async () => {
    // The backend answers [] rather than erroring, so "nothing connected" and
    // "connected but no models" look the same — which is what callers want.
    vi.mocked(fetch).mockResolvedValueOnce(okJson([]));
    expect(await listInferenceModels()).toEqual([]);
  });

  it("narrows to a task when asked", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson([]));

    await listInferenceModels(MASK_GENERATION_TASK);

    const url = vi.mocked(fetch).mock.calls[0][0] as string;
    expect(url).toContain(`task=${MASK_GENERATION_TASK}`);
  });

  it("passes models through", async () => {
    const models = [{ name: "sam2", task: MASK_GENERATION_TASK, provider_name: "local" }];
    vi.mocked(fetch).mockResolvedValueOnce(okJson(models));
    expect(await listInferenceModels()).toEqual(models);
  });
});

describe("generateImageMask", () => {
  const REQUEST = {
    model: "sam2",
    datasetId: "ds-1",
    viewId: "view-1",
    prompt: {
      points: [[10.4, 20.6] as [number, number]],
      labels: [1 as const],
    },
  };

  it("nests points and labels into the single batch the server expects", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [[]] } }));

    await generateImageMask(REQUEST);

    const body = sentBody();
    expect(body.points).toEqual([[[10, 21]]]);
    expect(body.labels).toEqual([[1]]);
  });

  it("rounds coordinates, which the server types as integers", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [[]] } }));

    await generateImageMask(REQUEST);

    const points = (sentBody().points as number[][][])[0];
    expect(points.every(([x, y]) => Number.isInteger(x) && Number.isInteger(y))).toBe(true);
  });

  it("uses the snake_case field names of the request model", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [[]] } }));

    await generateImageMask(REQUEST);

    const body = sentBody();
    expect(body.dataset_id).toBe("ds-1");
    expect(body.view_id).toBe("view-1");
    expect(body.model).toBe("sam2");
  });

  it("sends a box only when one was given", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [[]] } }));
    await generateImageMask(REQUEST);
    expect(sentBody().boxes).toBeNull();

    vi.mocked(fetch).mockClear();
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [[]] } }));
    await generateImageMask({
      ...REQUEST,
      prompt: { ...REQUEST.prompt, box: [1.2, 2.7, 3, 4] },
    });
    expect(sentBody().boxes).toEqual([[1, 3, 3, 4]]);
  });

  it("returns the first batch's masks", async () => {
    const masks = [{ size: [4, 6], counts: "a2b1" }];
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: { masks: [masks, []] } }));

    expect(await generateImageMask(REQUEST)).toEqual(masks);
  });

  it("returns an empty list when the response carries no masks", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(okJson({ data: {} }));
    expect(await generateImageMask(REQUEST)).toEqual([]);
  });

  it("throws ApiError on HTTP error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(errResponse(503, "Service Unavailable"));
    await expect(generateImageMask(REQUEST)).rejects.toBeInstanceOf(ApiError);
  });
});
