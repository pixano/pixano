/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import * as maskNormalization from "$lib/segmentation/maskNormalization";
import { Sam2VideoTracker } from "$lib/trackers";
import { ShapeType, type SaveMaskShape } from "$lib/types/shapeTypes";

function makeMask(frameIndex: number): SaveMaskShape {
  return {
    status: "saving",
    type: ShapeType.mask,
    viewRef: { id: `frame-${frameIndex}`, name: "camera" },
    itemId: "item-1",
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

describe("Sam2VideoTracker", () => {
  it("returns exact keyframes and nearest propagated masks", () => {
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera");
    tracker.addKeyframe({
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [], box: null },
      mask: makeMask(2),
    });
    tracker.addKeyframe({
      frameIndex: 8,
      viewRef: { id: "frame-8", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [], box: null },
      mask: makeMask(8),
    });

    const internalTracker = tracker as unknown as {
      propagatedMasks: Map<number, SaveMaskShape>;
      propagatedMaskSources: Map<number, number>;
    };
    internalTracker.propagatedMasks.set(5, makeMask(5));
    internalTracker.propagatedMaskSources.set(5, 2);
    internalTracker.propagatedMasks.set(7, makeMask(7));
    internalTracker.propagatedMaskSources.set(7, 8);

    const exact = tracker.interpolateAt(2);
    expect(exact?.isKeyframe).toBe(true);
    expect(exact?.data.mask.viewRef.id).toBe("frame-2");

    const nearestFromLeft = tracker.interpolateAt(5);
    expect(nearestFromLeft?.isKeyframe).toBe(false);
    expect(nearestFromLeft?.data.sourceKeyframeIndex).toBe(2);
    expect(nearestFromLeft?.data.mask.viewRef.id).toBe("frame-5");

    const nearestFromRight = tracker.interpolateAt(7);
    expect(nearestFromRight?.isKeyframe).toBe(false);
    expect(nearestFromRight?.data.sourceKeyframeIndex).toBe(8);
    expect(nearestFromRight?.data.mask.viewRef.id).toBe("frame-7");
  });

  it("builds a windowed tracking request with dataset metadata", async () => {
    const trackingClient = vi.fn().mockResolvedValue({
      data: {
        objects_ids: [1],
        frame_indexes: [],
        masks: [],
      },
    });
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera", trackingClient);
    tracker.setFrameSources([
      {
        frameIndex: 0,
        viewRef: { id: "frame-0", name: "camera" },
        width: 8,
        height: 8,
      },
      {
        frameIndex: 1,
        viewRef: { id: "frame-1", name: "camera" },
        width: 8,
        height: 8,
      },
    ]);

    await tracker.propagateFromKeyframe({
      frameIndex: 1,
      viewRef: { id: "frame-1", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      mask: makeMask(1),
    });

    expect(trackingClient).toHaveBeenCalledWith({
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      record_id: "record-1",
      view_name: "camera",
      start_frame_index: 0,
      frame_count: 2,
      objects_ids: [1],
      prompt_frame_indexes: [1],
      points: [[[4, 4]]],
      labels: [[1]],
      boxes: null,
      propagate: true,
      interval: null,
      keyframes: [
        {
          frame_index: 1,
          points: [{ x: 4, y: 4, label: 1 }],
          box: null,
          mask: null,
        },
      ],
    });
  });

  it("serializes interval keyframes with a mask anchor", async () => {
    const trackingClient = vi.fn().mockResolvedValue({
      data: {
        objects_ids: [1],
        frame_indexes: [],
        masks: [],
      },
    });
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera", trackingClient);
    tracker.setFrameSources([
      {
        frameIndex: 2,
        viewRef: { id: "frame-2", name: "camera" },
        width: 8,
        height: 8,
      },
      {
        frameIndex: 3,
        viewRef: { id: "frame-3", name: "camera" },
        width: 8,
        height: 8,
      },
      {
        frameIndex: 4,
        viewRef: { id: "frame-4", name: "camera" },
        width: 8,
        height: 8,
      },
    ]);

    await tracker.propagateInterval(2, 4, {
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [], box: null, mask: makeMask(2) },
      mask: makeMask(2),
    });

    expect(trackingClient).toHaveBeenCalledWith({
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      record_id: "record-1",
      view_name: "camera",
      start_frame_index: 2,
      frame_count: 3,
      objects_ids: [1],
      prompt_frame_indexes: [2],
      points: null,
      labels: null,
      boxes: null,
      propagate: true,
      interval: {
        start_frame: 2,
        end_frame: 4,
        direction: "forward",
      },
      keyframes: [
        {
          frame_index: 2,
          points: [],
          box: null,
          mask: {
            counts: [4, 8, 52],
            size: [8, 8],
          },
        },
      ],
    });
  });

  it("uses a single-frame non-propagating request for prompted-frame previews", async () => {
    const trackingClient = vi.fn().mockResolvedValue({
      data: {
        objects_ids: [1],
        frame_indexes: [],
        masks: [],
      },
    });
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera", trackingClient);
    tracker.setFrameSources([
      {
        frameIndex: 5,
        viewRef: { id: "frame-5", name: "camera" },
        width: 8,
        height: 8,
      },
      {
        frameIndex: 6,
        viewRef: { id: "frame-6", name: "camera" },
        width: 8,
        height: 8,
      },
    ]);

    await tracker.predictKeyframe({
      frameIndex: 5,
      viewRef: { id: "frame-5", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
    });

    expect(trackingClient).toHaveBeenCalledWith({
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      record_id: "record-1",
      view_name: "camera",
      start_frame_index: 5,
      frame_count: 1,
      objects_ids: [1],
      prompt_frame_indexes: [5],
      points: [[[4, 4]]],
      labels: [[1]],
      boxes: null,
      propagate: false,
      interval: null,
      keyframes: [
        {
          frame_index: 5,
          points: [{ x: 4, y: 4, label: 1 }],
          box: null,
          mask: null,
        },
      ],
    });
  });

  it("submits async tracking jobs with the same serialized request contract", async () => {
    const trackingClient = vi.fn();
    const submitTrackingJobClient = vi.fn().mockResolvedValue({
      job_id: "tracking-job-1",
      status: "running",
      detail: null,
      data: null,
    });
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera", trackingClient, {
      submitTrackingJobClient,
    });
    tracker.setFrameSources([
      {
        frameIndex: 5,
        viewRef: { id: "frame-5", name: "camera" },
        width: 8,
        height: 8,
      },
      {
        frameIndex: 6,
        viewRef: { id: "frame-6", name: "camera" },
        width: 8,
        height: 8,
      },
    ]);

    await tracker.submitPredictKeyframeJob({
      frameIndex: 5,
      viewRef: { id: "frame-5", name: "camera" },
      objectId: 1,
      model: "sam2",
      providerName: "pixano-inference@127.0.0.1:7463",
      itemId: "item-1",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
    });

    expect(submitTrackingJobClient).toHaveBeenCalledWith({
      model: "sam2",
      provider_name: "pixano-inference@127.0.0.1:7463",
      dataset_id: "dataset-1",
      record_id: "record-1",
      view_name: "camera",
      start_frame_index: 5,
      frame_count: 1,
      objects_ids: [1],
      prompt_frame_indexes: [5],
      points: [[[4, 4]]],
      labels: [[1]],
      boxes: null,
      propagate: false,
      interval: null,
      keyframes: [
        {
          frame_index: 5,
          points: [{ x: 4, y: 4, label: 1 }],
          box: null,
          mask: null,
        },
      ],
    });
  });

  it("applies completed async tracking results to propagated masks", () => {
    vi.spyOn(maskNormalization, "normalizeMaskToSaveShape").mockReturnValue(makeMask(5));
    const tracker = new Sam2VideoTracker("dataset-1", "record-1", "camera");
    tracker.setFrameSources([
      {
        frameIndex: 5,
        viewRef: { id: "frame-5", name: "camera" },
        width: 8,
        height: 8,
      },
    ]);

    const masks = tracker.applyTrackingResult(
      {
        objects_ids: [1],
        frame_indexes: [5],
        masks: [{ size: [8, 8], counts: [4, 8, 52] }],
      },
      {
        frameIndex: 5,
        viewRef: { id: "frame-5", name: "camera" },
        objectId: 1,
        model: "sam2",
        providerName: "pixano-inference@127.0.0.1:7463",
        itemId: "item-1",
        prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      },
    );

    expect(masks).toHaveLength(1);
    expect(tracker.getPropagatedMask(5)?.viewRef.id).toBe("frame-5");
    expect(tracker.getTrackingOutputsInRange(5, 5)[0]?.data.source_type).toBe("model");
    expect(tracker.getTrackingOutputsInRange(5, 5)[0]?.data.source_name).toBe("sam2");
  });
});
