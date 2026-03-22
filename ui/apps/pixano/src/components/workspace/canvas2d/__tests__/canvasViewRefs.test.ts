/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { resolveCanvasViewRef } from "../canvasViewRefs";

describe("resolveCanvasViewRef", () => {
  it("prefers the canonical current SequenceFrame ref when available", () => {
    expect(
      resolveCanvasViewRef("camera", "camera_12", {
        camera: { id: "frame-view-12", name: "camera" },
      }),
    ).toEqual({
      id: "frame-view-12",
      name: "camera",
    });
  });

  it("falls back to the loaded image id outside video SequenceFrame mode", () => {
    expect(resolveCanvasViewRef("camera", "image-view-1")).toEqual({
      id: "image-view-1",
      name: "camera",
    });
  });
});
