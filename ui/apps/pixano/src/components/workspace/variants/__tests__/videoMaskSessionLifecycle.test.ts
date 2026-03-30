/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  resolveVideoMaskResetAction,
  shouldClearVideoMaskSessionOnToolSwitch,
  shouldHydrateVideoPreview,
} from "../videoMaskSessionLifecycle";
import { ToolType } from "$lib/tools";
import { ShapeType, type Shape } from "$lib/types/shapeTypes";

function makeResetShape(partial?: Partial<Extract<Shape, { status: "none" }>>): Shape {
  return {
    status: "none",
    shouldReset: true,
    resetReason: "save-confirmed",
    resetShapeType: ShapeType.mask,
    resetViewRef: { id: "frame-4", name: "camera" },
    ...partial,
  };
}

describe("videoMaskSessionLifecycle", () => {
  it("resets the full smart-tracking session when a saved mask still has a live VOS session", () => {
    expect(
      resolveVideoMaskResetAction(makeResetShape(), {
        isVosSessionActive: true,
        hasTracker: true,
        hasActiveJob: false,
      }),
    ).toBe("reset-smart-tracking");
  });

  it("falls back to clearing only the preview when no live VOS session remains", () => {
    expect(
      resolveVideoMaskResetAction(makeResetShape(), {
        isVosSessionActive: false,
        hasTracker: false,
        hasActiveJob: false,
      }),
    ).toBe("clear-preview");
  });

  it("ignores non-mask or non-reset idle states", () => {
    expect(
      resolveVideoMaskResetAction(
        makeResetShape({ shouldReset: false, resetShapeType: ShapeType.bbox }),
        {
          isVosSessionActive: true,
          hasTracker: true,
          hasActiveJob: true,
        },
      ),
    ).toBe("ignore");
  });

  it("clears stale video mask sessions whenever the user leaves the VOS tool", () => {
    expect(
      shouldClearVideoMaskSessionOnToolSwitch(ToolType.Pan, {
        isVosSessionActive: false,
        hasTracker: true,
        hasActiveJob: false,
      }),
    ).toBe(true);
    expect(
      shouldClearVideoMaskSessionOnToolSwitch(ToolType.VOS, {
        isVosSessionActive: true,
        hasTracker: true,
        hasActiveJob: true,
      }),
    ).toBe(false);
  });

  it("hydrates frame-follow previews only while the VOS tool still owns a live session", () => {
    expect(
      shouldHydrateVideoPreview(ToolType.VOS, {
        isVosSessionActive: true,
        hasTracker: false,
        hasActiveJob: false,
      }),
    ).toBe(true);
    expect(
      shouldHydrateVideoPreview(ToolType.Pan, {
        isVosSessionActive: true,
        hasTracker: true,
        hasActiveJob: false,
      }),
    ).toBe(false);
  });
});
