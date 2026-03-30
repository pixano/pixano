/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { resolveSequenceFrameRef, resolveVideoFrameIdentity } from "$lib/utils/videoFrameIdentity";
import { BaseSchema, SequenceFrame } from "$lib/types/dataset";

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
      resolveSequenceFrameRef("camera", 1, frames, { id: "camera-frame-0", name: "camera" }),
    ).toEqual({ id: "camera-frame-1", name: "camera" });
  });

  it("normalizes a video annotation identity onto the active frame", () => {
    const frames = [makeFrame("camera", 0), makeFrame("camera", 1), makeFrame("camera", 2)];

    expect(
      resolveVideoFrameIdentity({ id: "camera-frame-0", name: "camera" }, 2, frames),
    ).toEqual({
      viewRef: { id: "camera-frame-2", name: "camera" },
      frameIndex: 2,
    });
  });
});
