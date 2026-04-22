/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { buildCurrentSequenceFrameLocatorsByView } from "../videoSequenceFrameRefs";

describe("buildCurrentSequenceFrameLocatorsByView", () => {
  it("returns canonical refs for the displayed frame index across views", () => {
    expect(
      buildCurrentSequenceFrameLocatorsByView(
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
      camera: { frameId: "camera-frame-1", logicalName: "camera", frameIndex: 1 },
      thermal: { frameId: "thermal-frame-1", logicalName: "thermal", frameIndex: 1 },
    });
  });

  it("skips views that do not contain the displayed frame", () => {
    expect(
      buildCurrentSequenceFrameLocatorsByView(
        {
          camera: [{ id: "camera-frame-0", data: { frame_index: 0 } }],
        },
        3,
      ),
    ).toEqual({});
  });
});
