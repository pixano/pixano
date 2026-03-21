import { describe, expect, it } from "vitest";

import { computeCursorFlushAction, computeToolChangeAction } from "../canvasEventHandlers";
import { brushDrawTool, interactiveSegmenterTool, panTool } from "$lib/tools/canvasToolPolicy";

describe("canvasEventHandlers", () => {
  it("shows the smart prompt cursor only for the interactive segmenter", () => {
    expect(computeCursorFlushAction(interactiveSegmenterTool)).toMatchObject({
      showCrosshair: true,
      showBrushCursor: false,
      showSmartPromptCursor: true,
    });

    expect(computeCursorFlushAction(brushDrawTool)).toMatchObject({
      showCrosshair: true,
      showBrushCursor: true,
      showSmartPromptCursor: false,
    });

    expect(computeCursorFlushAction(panTool)).toMatchObject({
      showCrosshair: false,
      showBrushCursor: false,
      showSmartPromptCursor: false,
    });
  });

  it("clears the smart prompt cursor when leaving the interactive segmenter", () => {
    expect(computeToolChangeAction(interactiveSegmenterTool).clearSmartPromptCursor).toBe(false);
    expect(computeToolChangeAction(brushDrawTool).clearSmartPromptCursor).toBe(true);
    expect(computeToolChangeAction(panTool).clearSmartPromptCursor).toBe(true);
  });
});
