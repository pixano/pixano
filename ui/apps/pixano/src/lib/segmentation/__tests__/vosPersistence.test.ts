/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { saveMaskShapeToTrackingOutput } from "$lib/segmentation/maskNormalization";
import { buildPersistedVosMasks } from "$lib/segmentation/vosPersistence";
import { BaseSchema, WorkspaceType } from "$lib/types/dataset";
import { ShapeType, type SaveMaskShape } from "$lib/types/shapeTypes";

function makeMask(frameIndex: number, counts: number[]): SaveMaskShape {
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
      counts,
      size: [8, 8],
    },
  };
}

describe("buildPersistedVosMasks", () => {
  it("materializes one persisted mask per frame from immutable session snapshots", () => {
    const sessionMasks = [
      {
        frameIndex: 2,
        segmentId: 1,
        output: saveMaskShapeToTrackingOutput(makeMask(2, [2, 4, 58]), 2),
      },
      {
        frameIndex: 4,
        segmentId: 1,
        output: saveMaskShapeToTrackingOutput(makeMask(4, [4, 6, 54]), 4),
      },
      {
        frameIndex: 6,
        segmentId: 1,
        output: saveMaskShapeToTrackingOutput(makeMask(6, [6, 8, 50]), 6),
      },
    ];

    const built = buildPersistedVosMasks({
      sessionMasks,
      currentFrameIndex: 6,
      entityId: "entity-1",
      tableInfo: {
        name: "masks",
        group: "annotations",
        base_schema: BaseSchema.Mask,
      },
      uiTemplate: {
        datasetItemType: WorkspaceType.VIDEO,
        displayControl: { hidden: false, editing: false, highlighted: "self" },
        top_entities: [],
      },
      fallbackSource: {
        modelName: "sam2-video",
        providerName: "pixano-inference",
      },
    });

    expect(built.currentMask?.data.frame_index).toBe(6);
    expect(built.trackingMasks.map((mask) => mask.data.frame_index)).toEqual([2, 4]);
    expect(built.allMasks).toHaveLength(3);
    expect(new Set(built.allMasks.map((mask) => mask.id)).size).toBe(3);
    expect(built.trackingMasks[0]?.data.counts as number[]).toEqual([2, 4, 58]);
    expect(built.trackingMasks[1]?.data.counts as number[]).toEqual([4, 6, 54]);
    expect(built.currentMask?.data.counts as number[]).toEqual([6, 8, 50]);

    (sessionMasks[0].output.data.counts as number[])[0] = 999;
    expect(built.trackingMasks[0]?.data.counts as number[]).toEqual([2, 4, 58]);
  });
});
