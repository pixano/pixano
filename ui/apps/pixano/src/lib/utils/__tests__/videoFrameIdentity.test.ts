/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { BaseSchema, SequenceFrame } from "$lib/types/dataset";
import {
  resolveSequenceFrameLocator,
  resolveVideoFrameIdentity,
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
