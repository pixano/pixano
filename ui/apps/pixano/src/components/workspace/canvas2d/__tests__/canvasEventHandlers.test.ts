/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  computeCursorFlushAction,
  computeToolChangeAction,
  resolveNeutralPeekPresentation,
  resolveInteractiveToolResetAction,
  shouldClearHighlightingOnPanCanvasClick,
  shouldHideAnnotationsForToolMode,
  shouldRenderAnnotationWhileToolHidden,
} from "../canvasEventHandlers";
import {
  NEUTRAL_ENTITY_COLOR,
  NOT_ANNOTATION_ITEM_OPACITY,
  PEEK_NEUTRAL_ANNOTATION_OPACITY,
  PEEK_NEUTRAL_ENTITY_COLOR,
  PEEK_NEUTRAL_MASK_OVERLAY_ALPHA,
} from "$lib/constants/workspaceConstants";
import { brushDrawTool, interactiveSegmenterTool, panTool } from "$lib/tools/canvasToolPolicy";
import { ToolType } from "$lib/tools";
import { ShapeType } from "$lib/types/shapeTypes";

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

  it("keeps non-peek hidden annotations on the current neutral defaults", () => {
    expect(
      resolveNeutralPeekPresentation({
        isPeeking: false,
        highlighted: "none",
        baseOpacity: NOT_ANNOTATION_ITEM_OPACITY,
      }),
    ).toEqual({
      neutralColor: NEUTRAL_ENTITY_COLOR,
      opacity: NOT_ANNOTATION_ITEM_OPACITY,
      maskOverlayAlpha: null,
    });
  });

  it("makes Alt-peek hidden annotations more visible without changing their neutral styling", () => {
    expect(
      resolveNeutralPeekPresentation({
        isPeeking: true,
        highlighted: "none",
        baseOpacity: NOT_ANNOTATION_ITEM_OPACITY,
      }),
    ).toEqual({
      neutralColor: PEEK_NEUTRAL_ENTITY_COLOR,
      opacity: PEEK_NEUTRAL_ANNOTATION_OPACITY,
      maskOverlayAlpha: null,
    });
  });

  it("uses the stronger Alt-peek neutral overlay for masks", () => {
    expect(
      resolveNeutralPeekPresentation({
        isPeeking: true,
        highlighted: "none",
        baseOpacity: NOT_ANNOTATION_ITEM_OPACITY,
        shapeKind: "mask",
      }),
    ).toEqual({
      neutralColor: PEEK_NEUTRAL_ENTITY_COLOR,
      opacity: PEEK_NEUTRAL_ANNOTATION_OPACITY,
      maskOverlayAlpha: PEEK_NEUTRAL_MASK_OVERLAY_ALPHA,
    });
  });

  it("leaves self-highlighted annotations unchanged outside Alt peek", () => {
    expect(
      resolveNeutralPeekPresentation({
        isPeeking: false,
        highlighted: "self",
        baseOpacity: 1,
      }),
    ).toEqual({
      neutralColor: NEUTRAL_ENTITY_COLOR,
      opacity: 1,
      maskOverlayAlpha: null,
    });
  });

  it("preserves local prompt previews only for cancelled interactive mask resets", () => {
    expect(
      resolveInteractiveToolResetAction(ToolType.VOS, "save-cancelled", ShapeType.mask),
    ).toBe("preserve-local-preview");
    expect(
      resolveInteractiveToolResetAction(
        ToolType.InteractiveSegmenter,
        "save-cancelled",
        ShapeType.mask,
      ),
    ).toBe("preserve-local-preview");
  });

  it("reinitializes interactive tools locally after a confirmed mask save without AI cancel", () => {
    expect(
      resolveInteractiveToolResetAction(ToolType.VOS, "save-confirmed", ShapeType.mask),
    ).toBe("reset-local-interactive-tool");
    expect(
      resolveInteractiveToolResetAction(
        ToolType.InteractiveSegmenter,
        "save-confirmed",
        ShapeType.mask,
      ),
    ).toBe("reset-local-interactive-tool");
  });

  it("ignores non-mask and non-interactive reset states", () => {
    expect(
      resolveInteractiveToolResetAction(ToolType.VOS, "save-confirmed", ShapeType.bbox),
    ).toBe("none");
    expect(resolveInteractiveToolResetAction(ToolType.Pan, "save-confirmed", ShapeType.mask)).toBe(
      "none",
    );
    expect(resolveInteractiveToolResetAction(undefined, undefined, undefined)).toBe("none");
  });
});
