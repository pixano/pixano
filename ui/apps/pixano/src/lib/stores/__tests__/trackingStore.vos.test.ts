/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { beforeEach, describe, expect, it } from "vitest";

import { saveMaskShapeToTrackingOutput } from "$lib/segmentation/maskNormalization";
import {
  NULL_VOS_STATE,
  beginVosPendingIntervalState,
  commitVosIntervalState,
  isVosSessionActiveState,
  setVosAnchorState,
  startNewVosSegmentState,
  type VosSessionState,
} from "$lib/stores/vosSession";
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

describe("vosSession", () => {
  let state: VosSessionState;

  beforeEach(() => {
    state = { ...NULL_VOS_STATE };
  });

  it("extends one visible segment across repeated T intervals", () => {
    state = setVosAnchorState(state, {
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      sourceKind: "prompt",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      mask: makeMask(2),
    });

    state = beginVosPendingIntervalState(state, {
      requestId: "track-1",
      startFrame: 2,
      endFrame: 4,
      direction: "forward",
    });
    state = commitVosIntervalState(state, {
      requestId: "track-1",
      outputs: [2, 3, 4].map((frameIndex) => saveMaskShapeToTrackingOutput(makeMask(frameIndex), frameIndex)),
      nextAnchor: {
        frameIndex: 4,
        viewRef: { id: "frame-4", name: "camera" },
        sourceKind: "mask",
        prompt: null,
        mask: makeMask(4),
      },
    });

    state = beginVosPendingIntervalState(state, {
      requestId: "track-2",
      startFrame: 4,
      endFrame: 6,
      direction: "forward",
    });
    state = commitVosIntervalState(state, {
      requestId: "track-2",
      outputs: [4, 5, 6].map((frameIndex) => saveMaskShapeToTrackingOutput(makeMask(frameIndex), frameIndex)),
      nextAnchor: {
        frameIndex: 6,
        viewRef: { id: "frame-6", name: "camera" },
        sourceKind: "mask",
        prompt: null,
        mask: makeMask(6),
      },
    });

    expect(state.anchor?.frameIndex).toBe(6);
    expect(state.segments).toHaveLength(1);
    expect(state.segments[0]).toMatchObject({
      startFrame: 2,
      endFrame: 6,
    });
    expect(state.masks.map((mask) => mask.frameIndex)).toEqual([2, 3, 4, 5, 6]);
    expect(isVosSessionActiveState(state)).toBe(true);
  });

  it("starts a later segment for the same object after N", () => {
    state = setVosAnchorState(state, {
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      sourceKind: "prompt",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      mask: makeMask(2),
    });

    state = beginVosPendingIntervalState(state, {
      requestId: "track-1",
      startFrame: 2,
      endFrame: 4,
      direction: "forward",
    });
    state = commitVosIntervalState(state, {
      requestId: "track-1",
      outputs: [2, 3, 4].map((frameIndex) => saveMaskShapeToTrackingOutput(makeMask(frameIndex), frameIndex)),
      nextAnchor: {
        frameIndex: 4,
        viewRef: { id: "frame-4", name: "camera" },
        sourceKind: "mask",
        prompt: null,
        mask: makeMask(4),
      },
    });

    state = startNewVosSegmentState(state);
    state = setVosAnchorState(state, {
      frameIndex: 8,
      viewRef: { id: "frame-8", name: "camera" },
      sourceKind: "prompt",
      prompt: { points: [{ x: 5, y: 5, label: 1 }], box: null },
      mask: makeMask(8),
    });

    state = beginVosPendingIntervalState(state, {
      requestId: "track-2",
      startFrame: 8,
      endFrame: 9,
      direction: "forward",
    });
    state = commitVosIntervalState(state, {
      requestId: "track-2",
      outputs: [8, 9].map((frameIndex) => saveMaskShapeToTrackingOutput(makeMask(frameIndex), frameIndex)),
      nextAnchor: {
        frameIndex: 9,
        viewRef: { id: "frame-9", name: "camera" },
        sourceKind: "mask",
        prompt: null,
        mask: makeMask(9),
      },
    });

    expect(state.segments.map((segment) => [segment.startFrame, segment.endFrame])).toEqual([
      [2, 4],
      [8, 9],
    ]);
    expect(new Set(state.masks.map((mask) => mask.segmentId)).size).toBe(2);
  });

  it("preserves provided model provenance on the anchor output", () => {
    const output = saveMaskShapeToTrackingOutput(makeMask(2), 2, {
      modelName: "sam2-video",
      providerName: "pixano-inference",
    });

    state = setVosAnchorState(state, {
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      sourceKind: "prompt",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      mask: makeMask(2),
      output,
    });

    expect(state.masks[0]?.output.data.source_type).toBe("model");
    expect(state.masks[0]?.output.data.source_name).toBe("sam2-video");
    expect(state.masks[0]?.output.data.source_metadata).toBe(
      '{"provider_name":"pixano-inference"}',
    );
  });

  it("stores immutable output snapshots across anchor and interval updates", () => {
    const anchorOutput = saveMaskShapeToTrackingOutput(makeMask(2), 2);
    (anchorOutput.data.counts as number[])[0] = 21;

    state = setVosAnchorState(state, {
      frameIndex: 2,
      viewRef: { id: "frame-2", name: "camera" },
      sourceKind: "prompt",
      prompt: { points: [{ x: 4, y: 4, label: 1 }], box: null },
      mask: makeMask(2),
      output: anchorOutput,
    });

    (anchorOutput.data.counts as number[])[0] = 999;
    expect((state.masks[0]?.output.data.counts as number[])[0]).toBe(21);

    const intervalOutputs = [3, 4].map((frameIndex) => {
      const output = saveMaskShapeToTrackingOutput(makeMask(frameIndex), frameIndex);
      (output.data.counts as number[])[0] = frameIndex * 10;
      return output;
    });

    state = beginVosPendingIntervalState(state, {
      requestId: "track-1",
      startFrame: 2,
      endFrame: 4,
      direction: "forward",
    });
    state = commitVosIntervalState(state, {
      requestId: "track-1",
      outputs: intervalOutputs,
      nextAnchor: {
        frameIndex: 4,
        viewRef: { id: "frame-4", name: "camera" },
        sourceKind: "mask",
        prompt: null,
        mask: makeMask(4),
      },
    });

    (intervalOutputs[0].data.counts as number[])[0] = 777;
    expect((state.masks.find((mask) => mask.frameIndex === 2)?.output.data.counts as number[])[0]).toBe(
      21,
    );
    expect((state.masks.find((mask) => mask.frameIndex === 3)?.output.data.counts as number[])[0]).toBe(
      30,
    );
  });
});
