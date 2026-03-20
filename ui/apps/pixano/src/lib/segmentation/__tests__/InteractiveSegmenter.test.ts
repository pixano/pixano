import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImageSegmentationTaskInput, ImageSegmentationTaskResult } from "$lib/types/inference";
import { ShapeType, type SaveMaskShape } from "$lib/types/shapeTypes";

const { embeddingsMock } = vi.hoisted(() => ({
  embeddingsMock: {
    value: {} as Record<string, unknown>,
    update(updater: (current: Record<string, unknown>) => Record<string, unknown>) {
      this.value = updater(this.value);
    },
  },
}));

const { segmentImageMock, normalizeMaskToSaveShapeMock } = vi.hoisted(() => ({
  segmentImageMock: vi.fn<
    (input: ImageSegmentationTaskInput) => Promise<ImageSegmentationTaskResult>
  >(),
  normalizeMaskToSaveShapeMock: vi.fn<
    (args: { viewRef: { id: string; name: string }; itemId: string }) => SaveMaskShape
  >(),
}));

vi.mock("$lib/api/inferenceApi", () => ({
  segmentImage: segmentImageMock,
}));

vi.mock("$lib/stores/workspaceStores.svelte", () => ({
  embeddings: embeddingsMock,
}));

vi.mock("../maskNormalization", () => ({
  normalizeMaskToSaveShape: normalizeMaskToSaveShapeMock,
}));

import { InteractiveSegmenter } from "../InteractiveSegmenter";
import { toBoxPrompt } from "../promptSerialization";

const embeddings = embeddingsMock;

function makePreviewMask(viewId: string, viewName: string, itemId: string): SaveMaskShape {
  return {
    status: "saving",
    type: ShapeType.mask,
    viewRef: { id: viewId, name: viewName },
    itemId,
    imageWidth: 8,
    imageHeight: 8,
    maskDataUrl: "data:image/png;base64,AAAA",
    maskMimeType: "image/png",
    maskBounds: { x: 1, y: 1, width: 4, height: 4 },
    rle: {
      counts: [4, 8, 52],
      size: [8, 8],
    },
  };
}

function makeSegmentationResponse(options?: {
  imageEmbedding?: { values: number[]; shape: number[] } | null;
  highResolutionFeatures?: Array<{ values: number[]; shape: number[] }> | null;
  maskLogits?: { values: number[]; shape: number[] } | null;
}) {
  return {
    data: {
      masks: [[{ size: [8, 8], counts: [64] }]],
      scores: { values: [0.95], shape: [1, 1] },
      image_embedding: options?.imageEmbedding ?? null,
      high_resolution_features: options?.highResolutionFeatures ?? null,
      mask_logits: options?.maskLogits ?? null,
    },
    timestamp: "2026-03-20T10:00:00",
    processing_time: 0.12,
    metadata: { backend: "mock" },
    id: "seg-1",
    status: "SUCCESS",
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("InteractiveSegmenter", () => {
  beforeEach(() => {
    segmentImageMock.mockReset();
    normalizeMaskToSaveShapeMock.mockReset();
    normalizeMaskToSaveShapeMock.mockImplementation(
      (args: {
        viewRef: { id: string; name: string };
        itemId: string;
      }) => makePreviewMask(args.viewRef.id, args.viewRef.name, args.itemId),
    );
    embeddings.value = {};
  });

  it("rounds rectangle prompts to integer xyxy coordinates", () => {
    expect(
      toBoxPrompt({
        x: 10.4,
        y: 20.6,
        width: 30.2,
        height: 40.7,
      }),
    ).toEqual([[10, 21, 41, 61]]);
  });

  it("normalizes negative drag directions before serialization", () => {
    expect(
      toBoxPrompt({
        x: 50.9,
        y: 60.2,
        width: -20.6,
        height: -10.8,
      }),
    ).toEqual([[30, 49, 51, 60]]);
  });

  it("caches embeddings and low-resolution logits across refinement requests", async () => {
    const segmenter = new InteractiveSegmenter();
    segmentImageMock
      .mockResolvedValueOnce(
        makeSegmentationResponse({
          imageEmbedding: { values: [1, 2], shape: [1, 2] },
          highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
          maskLogits: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
        }),
      )
      .mockResolvedValueOnce(
        makeSegmentationResponse({
          maskLogits: { values: [0.4, 0.3, 0.2, 0.1], shape: [1, 2, 2] },
        }),
      );

    await segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [{ x: 10, y: 20, label: 1 }],
        box: null,
      },
    });

    await segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [
          { x: 10, y: 20, label: 1 },
          { x: 30, y: 40, label: 0 },
        ],
        box: null,
      },
    });

    expect(segmentImageMock).toHaveBeenNthCalledWith(1, {
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      view_id: "view-1",
      image_embedding: null,
      high_resolution_features: null,
      mask_input: null,
      reset_predictor: true,
      points: [[[10, 20]]],
      labels: [[1]],
      boxes: null,
      num_multimask_outputs: 1,
      multimask_output: false,
      return_image_embedding: true,
      return_logits: true,
    });
    expect(segmentImageMock).toHaveBeenNthCalledWith(2, {
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      view_id: "view-1",
      image_embedding: { values: [1, 2], shape: [1, 2] },
      high_resolution_features: [{ values: [0.5], shape: [1, 1] }],
      mask_input: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
      reset_predictor: true,
      points: [[[10, 20], [30, 40]]],
      labels: [[1, 0]],
      boxes: null,
      num_multimask_outputs: 1,
      multimask_output: false,
      return_image_embedding: false,
      return_logits: true,
    });
  });

  it("ignores stale responses when a newer refinement finishes first", async () => {
    const segmenter = new InteractiveSegmenter();
    const firstResponse = deferred<ReturnType<typeof makeSegmentationResponse>>();
    const secondResponse = deferred<ReturnType<typeof makeSegmentationResponse>>();
    segmentImageMock.mockReturnValueOnce(firstResponse.promise).mockReturnValueOnce(secondResponse.promise);

    const firstPrediction = segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [{ x: 10, y: 20, label: 1 }],
        box: null,
      },
    });

    const secondPrediction = segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [
          { x: 10, y: 20, label: 1 },
          { x: 12, y: 22, label: 1 },
        ],
        box: null,
      },
    });

    secondResponse.resolve(
      makeSegmentationResponse({
        imageEmbedding: { values: [1, 2], shape: [1, 2] },
        highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
        maskLogits: { values: [0.4, 0.3, 0.2, 0.1], shape: [1, 2, 2] },
      }),
    );
    firstResponse.resolve(
      makeSegmentationResponse({
        imageEmbedding: { values: [1, 2], shape: [1, 2] },
        highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
        maskLogits: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
      }),
    );

    const latest = await secondPrediction;
    const stale = await firstPrediction;

    expect(latest?.previewMask.viewRef.id).toBe("view-1");
    expect(stale).toBeNull();
  });

  it("uses binary masks for preview while caching low-resolution logits for refinement", async () => {
    const segmenter = new InteractiveSegmenter();
    const binaryMask = { size: [8, 8], counts: [64] };

    segmentImageMock.mockResolvedValueOnce({
      ...makeSegmentationResponse({
        imageEmbedding: { values: [1, 2], shape: [1, 2] },
        highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
        maskLogits: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
      }),
      data: {
        ...makeSegmentationResponse({
          imageEmbedding: { values: [1, 2], shape: [1, 2] },
          highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
          maskLogits: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
        }).data,
        masks: [[binaryMask]],
      },
    });

    await segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [{ x: 10, y: 20, label: 1 }],
        box: null,
      },
    });

    expect(normalizeMaskToSaveShapeMock).toHaveBeenCalledWith(
      expect.objectContaining({
        mask: binaryMask,
      }),
    );
    expect(segmentImageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        return_logits: true,
      }),
    );
  });

  it("uses the box only to seed the session before point refinement", async () => {
    const segmenter = new InteractiveSegmenter();
    segmentImageMock
      .mockResolvedValueOnce(
        makeSegmentationResponse({
          imageEmbedding: { values: [1, 2], shape: [1, 2] },
          highResolutionFeatures: [{ values: [0.5], shape: [1, 1] }],
          maskLogits: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
        }),
      )
      .mockResolvedValueOnce(
        makeSegmentationResponse({
          maskLogits: { values: [0.4, 0.3, 0.2, 0.1], shape: [1, 2, 2] },
        }),
      );

    await segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [],
        box: { x: 15, y: 25, width: 20, height: 10 },
      },
    });

    await segmenter.predictMask({
      datasetId: "dataset-1",
      viewRef: { id: "view-1", name: "camera" },
      itemId: "item-1",
      image: { width: 8, height: 8 },
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      prompt: {
        points: [{ x: 30, y: 35, label: 1 }],
        box: { x: 15, y: 25, width: 20, height: 10 },
      },
    });

    expect(segmentImageMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        mask_input: { values: [0.1, 0.2, 0.3, 0.4], shape: [1, 2, 2] },
        points: [[[30, 35]]],
        labels: [[1]],
        boxes: null,
      }),
    );
  });
});
