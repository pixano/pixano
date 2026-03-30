/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  computeCursorFlushAction,
  computeToolChangeAction,
  shouldClearHighlightingOnPanCanvasClick,
  shouldHideAnnotationsForToolMode,
  shouldRenderAnnotationWhileToolHidden,
} from "../canvasEventHandlers";
import { brushDrawTool, interactiveSegmenterTool, panTool } from "$lib/tools/canvasToolPolicy";
import { ToolType } from "$lib/tools";

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

  it("hides annotations while a drawing tool is active unless the user is peeking", () => {
    expect(shouldHideAnnotationsForToolMode(true, false)).toBe(true);
    expect(shouldHideAnnotationsForToolMode(true, true)).toBe(false);
    expect(shouldHideAnnotationsForToolMode(false, false)).toBe(false);
  });

  it("clears highlighting only for a left click on blank canvas while Pan is active", () => {
    expect(shouldClearHighlightingOnPanCanvasClick(panTool, 0)).toBe(true);
    expect(shouldClearHighlightingOnPanCanvasClick(panTool, 1)).toBe(false);
    expect(
      shouldClearHighlightingOnPanCanvasClick(
        { ...interactiveSegmenterTool, type: ToolType.VOS },
        0,
      ),
    ).toBe(false);
  });

  it("keeps only self-highlighted annotations visible while tool-hide is active", () => {
    expect(
      shouldRenderAnnotationWhileToolHidden({
        hidden: false,
        editing: false,
        highlighted: "self",
      }),
    ).toBe(true);

    expect(
      shouldRenderAnnotationWhileToolHidden({
        hidden: false,
        editing: false,
        highlighted: "none",
      }),
    ).toBe(false);
  });

  it("keeps editing annotations visible while tool-hide is active", () => {
    expect(
      shouldRenderAnnotationWhileToolHidden({
        hidden: false,
        editing: true,
        highlighted: "none",
      }),
    ).toBe(true);
  });

  it("never renders annotations explicitly hidden by display control in tool-hide mode", () => {
    expect(
      shouldRenderAnnotationWhileToolHidden({
        hidden: true,
        editing: true,
        highlighted: "self",
      }),
    ).toBe(false);
  });
});
