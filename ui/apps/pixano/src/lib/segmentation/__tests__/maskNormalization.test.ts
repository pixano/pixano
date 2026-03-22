/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  cloneTrackingMaskOutput,
  normalizeTrackingMaskOutputForPersistence,
  saveMaskShapeToTrackingOutput,
} from "$lib/segmentation/maskNormalization";
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

describe("maskNormalization", () => {
  it("builds tracking outputs with model provenance", () => {
    const output = saveMaskShapeToTrackingOutput(makeMask(2), 2, {
      modelName: "sam2-video",
      providerName: "pixano-inference",
    });

    expect(output.data.source_type).toBe("model");
    expect(output.data.source_name).toBe("sam2-video");
    expect(output.data.source_metadata).toBe('{"provider_name":"pixano-inference"}');
  });

  it("normalizes stale preview provenance before persistence", () => {
    const output = saveMaskShapeToTrackingOutput(makeMask(4), 4);
    output.data.source_type = "pixano";
    output.data.source_name = "smart-segmentation";
    output.data.source_metadata = "{}";

    const normalized = normalizeTrackingMaskOutputForPersistence(output, {
      modelName: "sam2-video",
      providerName: "pixano-inference",
    });

    expect(normalized.data.source_type).toBe("model");
    expect(normalized.data.source_name).toBe("sam2-video");
    expect(normalized.data.source_metadata).toBe('{"provider_name":"pixano-inference"}');
  });

  it("clones tracked mask arrays when creating outputs", () => {
    const mask = makeMask(5);
    const counts = mask.rle?.counts as number[];
    const size = mask.rle?.size as [number, number];

    const output = saveMaskShapeToTrackingOutput(mask, 5);
    counts[0] = 999;
    size[0] = 99;

    expect(output.data.counts).toEqual([4, 8, 52]);
    expect(output.data.size).toEqual([8, 8]);
  });

  it("deep-clones tracking outputs", () => {
    const output = saveMaskShapeToTrackingOutput(makeMask(7), 7);
    const cloned = cloneTrackingMaskOutput(output);

    (cloned.data.counts as number[])[0] = 123;
    cloned.data.size[0] = 77;

    expect(output.data.counts).toEqual([4, 8, 52]);
    expect(output.data.size).toEqual([8, 8]);
  });
});
