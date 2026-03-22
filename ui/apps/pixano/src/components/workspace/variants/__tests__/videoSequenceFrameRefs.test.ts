import { describe, expect, it } from "vitest";

import { buildCurrentSequenceFrameRefsByView } from "../videoSequenceFrameRefs";

describe("buildCurrentSequenceFrameRefsByView", () => {
  it("returns canonical refs for the displayed frame index across views", () => {
    expect(
      buildCurrentSequenceFrameRefsByView(
        {
          camera: [
            { id: "camera-frame-0", data: { frame_index: 0 } },
            { id: "camera-frame-1", data: { frame_index: 1 } },
          ],
          thermal: [
            { id: "thermal-frame-0", data: { frame_index: 0 } },
            { id: "thermal-frame-1", data: { frame_index: 1 } },
          ],
        },
        1,
      ),
    ).toEqual({
      camera: { id: "camera-frame-1", name: "camera" },
      thermal: { id: "thermal-frame-1", name: "thermal" },
    });
  });

  it("skips views that do not contain the displayed frame", () => {
    expect(
      buildCurrentSequenceFrameRefsByView(
        {
          camera: [{ id: "camera-frame-0", data: { frame_index: 0 } }],
        },
        3,
      ),
    ).toEqual({});
  });
});
