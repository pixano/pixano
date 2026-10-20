/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { BaseSchema, SequenceFrame } from "$lib/types/dataset";
import {
  findSequenceFrameByIndex,
  resolveSequenceFrameLocator,
  resolveVideoFrameIdentity,
  sequenceFrameRange,
} from "$lib/utils/videoFrameIdentity";

const NOW = "2026-03-29T00:00:00+00:00";

function makeFrame(viewName: string, frameIndex: number): SequenceFrame {
  return new SequenceFrame({
    id: `${viewName}-frame-${frameIndex}`,
    table_info: {
      name: "frames",
      group: "views",
      base_schema: BaseSchema.SequenceFrame,
    },
    created_at: NOW,
    updated_at: NOW,
    data: {
      item_id: "item-1",
      parent_id: "",
      view_name: viewName,
      url: "",
      width: 100,
      height: 100,
      format: "png",
      timestamp: frameIndex,
      frame_index: frameIndex,
    },
  });
}

describe("videoFrameIdentity", () => {
  it("resolves the currently visible sequence frame reference", () => {
    const frames = [makeFrame("camera", 0), makeFrame("camera", 1), makeFrame("camera", 2)];

    expect(
      resolveSequenceFrameLocator("camera", 1, frames, {
        id: "camera-frame-0",
        logicalName: "camera",
      }),
    ).toEqual({ frameId: "camera-frame-1", logicalName: "camera", frameIndex: 1 });
  });

  it("normalizes a video annotation identity onto the active frame", () => {
    const frames = [makeFrame("camera", 0), makeFrame("camera", 1), makeFrame("camera", 2)];

    expect(
      resolveVideoFrameIdentity({ id: "camera-frame-0", logicalName: "camera" }, 2, frames),
    ).toEqual({
      frameLocator: { frameId: "camera-frame-2", logicalName: "camera", frameIndex: 2 },
      frameIndex: 2,
    });
  });
});

describe("findSequenceFrameByIndex", () => {
  const dense = [0, 1, 2, 3].map((index) => makeFrame("cam", index));
  const sparse = [0, 1, 2, 4].map((index) => makeFrame("cam", index));
  const offset = [5, 6, 7].map((index) => makeFrame("cam", index));

  it("finds a frame by its frame_index", () => {
    expect(findSequenceFrameByIndex(dense, 2)?.id).toBe("cam-frame-2");
    expect(findSequenceFrameByIndex(sparse, 4)?.id).toBe("cam-frame-4");
    expect(findSequenceFrameByIndex(offset, 6)?.id).toBe("cam-frame-6");
  });

  it("never falls back to the array position", () => {
    expect(findSequenceFrameByIndex(sparse, 3)).toBeUndefined();
    expect(findSequenceFrameByIndex(offset, 0)).toBeUndefined();
    expect(findSequenceFrameByIndex(offset, 2)).toBeUndefined();
  });

  it("rejects missing views and invalid indexes", () => {
    expect(findSequenceFrameByIndex(undefined, 0)).toBeUndefined();
    expect(findSequenceFrameByIndex(dense, 1.5)).toBeUndefined();
    expect(findSequenceFrameByIndex(dense, -1)).toBeUndefined();
  });
});

describe("sequenceFrameRange", () => {
  it("spans the view's frame indexes, clamped to the clip", () => {
    const frames = [5, 6, 7, 9].map((index) => makeFrame("cam", index));
    expect(sequenceFrameRange(frames)).toEqual({ first: 5, last: 9 });
    expect(sequenceFrameRange(frames, 8)).toEqual({ first: 5, last: 8 });
  });

  it("is null for an empty view or a view past the clip", () => {
    expect(sequenceFrameRange([])).toBeNull();
    expect(sequenceFrameRange(undefined)).toBeNull();
    expect(sequenceFrameRange([makeFrame("cam", 9)], 5)).toBeNull();
  });
});
