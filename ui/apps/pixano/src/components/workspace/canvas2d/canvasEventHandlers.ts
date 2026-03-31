/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  NEUTRAL_ENTITY_COLOR,
  PEEK_NEUTRAL_ANNOTATION_OPACITY,
  PEEK_NEUTRAL_ENTITY_COLOR,
  PEEK_NEUTRAL_MASK_OVERLAY_ALPHA,
} from "$lib/constants/workspaceConstants";
import { ToolType, type SelectionTool } from "$lib/tools";
import { ShapeType } from "$lib/types/shapeTypes";
import {
  interactiveSegmenterTool,
  panTool,
  polygonTool,
  polylineTool,
  rectangleTool,
} from "$lib/tools/canvasToolPolicy";

/**
 * Computes a stable signature for a tool configuration.
 * Used to detect meaningful tool switches (ignoring no-ops).
 */
export function getToolSwitchSignature(tool: SelectionTool): string {
  if (tool.type === ToolType.Brush) {
    return `${tool.type}:${tool.mode}`;
  }
  if (tool.type === ToolType.Polygon) {
    return `${tool.type}:${tool.outputMode}`;
  }
  if (tool.type === ToolType.Rectangle) {
    return `${tool.type}:${tool.isSmart ? "smart" : "regular"}`;
  }
  if (tool.type === ToolType.InteractiveSegmenter || tool.type === ToolType.VOS) {
    return tool.type;
  }
  return tool.type;
}

/**
 * Describes the overlay/cursor state changes needed when switching tools.
 */
export interface ToolChangeAction {
  cursor: string;
  clearCrosshair: boolean;
  clearBrushCursor: boolean;
  clearSmartPromptCursor: boolean;
  cleanupPolygonPreview: boolean;
}

/**
 * Compute the side effects needed when the active tool changes.
 * Returns a pure description — caller applies the actual state mutations.
 */
export function computeToolChangeAction(tool: SelectionTool | undefined): ToolChangeAction {
  if (tool?.type === ToolType.Pan) {
    return {
      cursor: panTool.cursor,
      clearCrosshair: true,
      clearBrushCursor: true,
      clearSmartPromptCursor: true,
      cleanupPolygonPreview: true,
    };
  }
  if (tool?.type === ToolType.Rectangle) {
    return {
      cursor: rectangleTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      clearSmartPromptCursor: true,
      cleanupPolygonPreview: true,
    };
  }
  if (tool?.type === ToolType.InteractiveSegmenter || tool?.type === ToolType.VOS) {
    return {
      cursor: interactiveSegmenterTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      clearSmartPromptCursor: false,
      cleanupPolygonPreview: true,
    };
  }
  if (tool?.type === ToolType.Polygon) {
    return {
      cursor: polygonTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      clearSmartPromptCursor: true,
      cleanupPolygonPreview: false,
    };
  }
  if (tool?.type === ToolType.Polyline) {
    return {
      cursor: polylineTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      clearSmartPromptCursor: true,
      cleanupPolygonPreview: false,
    };
  }
  if (tool?.type === ToolType.Brush) {
    return {
      cursor: "none",
      clearCrosshair: true,
      clearBrushCursor: false,
      clearSmartPromptCursor: true,
      cleanupPolygonPreview: true,
    };
  }
  // Default / unknown tool
  return {
    cursor: "default",
    clearCrosshair: true,
    clearBrushCursor: true,
    clearSmartPromptCursor: true,
    cleanupPolygonPreview: true,
  };
}

/**
 * Describes the cursor overlay state changes for a pointer-move frame flush.
 */
export interface CursorFlushAction {
  showCrosshair: boolean;
  showBrushCursor: boolean;
  showSmartPromptCursor: boolean;
}

export interface AnnotationToolHideDisplayControl {
  hidden?: boolean;
  editing?: boolean;
  highlighted?: "all" | "self" | "none";
}

export interface NeutralPeekPresentationInput {
  isPeeking: boolean;
  highlighted?: "all" | "self" | "none";
  baseOpacity: number;
  shapeKind?: "generic" | "mask";
}

export interface NeutralPeekPresentation {
  neutralColor: string;
  opacity: number;
  maskOverlayAlpha: number | null;
}

const DEFAULT_NEUTRAL_MASK_OVERLAY_ALPHA = 0.2;

/**
 * Existing annotations are hidden while a drawing tool is active unless the user is peeking.
 */
export function shouldHideAnnotationsForToolMode(isDrawingTool: boolean, isPeeking: boolean): boolean {
  return isDrawingTool && !isPeeking;
}

/**
 * A left click on the blank canvas while Pan is active should clear all annotation highlighting.
 */
export function shouldClearHighlightingOnPanCanvasClick(
  tool: SelectionTool | undefined,
  button: number,
): boolean {
  return tool?.type === ToolType.Pan && button === 0;
}

/**
 * While a drawing tool is active, keep only the selected/self-highlighted annotation (or any
 * annotation already in editing mode) visible.
 */
export function shouldRenderAnnotationWhileToolHidden(
  control: AnnotationToolHideDisplayControl,
): boolean {
  return !control.hidden && (control.highlighted === "self" || control.editing === true);
}

/**
 * Resolve the transient render overrides used while Alt-peeking hidden annotations.
 * This never mutates store state; it only describes how the current render pass should look.
 */
export function resolveNeutralPeekPresentation(
  input: NeutralPeekPresentationInput,
): NeutralPeekPresentation {
  const isNeutralPeek = input.isPeeking && input.highlighted === "none";

  return {
    neutralColor: input.isPeeking ? PEEK_NEUTRAL_ENTITY_COLOR : NEUTRAL_ENTITY_COLOR,
    opacity: isNeutralPeek ? Math.max(input.baseOpacity, PEEK_NEUTRAL_ANNOTATION_OPACITY) : input.baseOpacity,
    maskOverlayAlpha:
      input.shapeKind === "mask"
        ? input.isPeeking
          ? PEEK_NEUTRAL_MASK_OVERLAY_ALPHA
          : DEFAULT_NEUTRAL_MASK_OVERLAY_ALPHA
        : null,
  };
}

export type InteractiveToolResetAction =
  | "none"
  | "preserve-local-preview"
  | "reset-local-interactive-tool";

/**
 * Determines how Canvas2D should handle local interactive-tool cleanup for a one-shot reset state.
 * This intentionally describes only local canvas/FSM behavior and must not inspect live bridge state.
 */
export function resolveInteractiveToolResetAction(
  toolType: ToolType | undefined,
  resetReason: "save-confirmed" | "save-cancelled" | undefined,
  resetShapeType: ShapeType | undefined,
): InteractiveToolResetAction {
  const isInteractiveTool =
    toolType === ToolType.InteractiveSegmenter || toolType === ToolType.VOS;
  if (!isInteractiveTool || resetShapeType !== ShapeType.mask) {
    return "none";
  }
  if (resetReason === "save-cancelled") {
    return "preserve-local-preview";
  }
  if (resetReason === "save-confirmed") {
    return "reset-local-interactive-tool";
  }
  return "none";
}

/**
 * Compute which cursor overlays should be active for the current tool.
 * The actual position/state updates are done by the caller.
 */
export function computeCursorFlushAction(tool: SelectionTool | undefined): CursorFlushAction {
  const isDrawTool =
    tool?.type === ToolType.Rectangle ||
    tool?.type === ToolType.InteractiveSegmenter ||
    tool?.type === ToolType.VOS ||
    tool?.type === ToolType.Polygon ||
    tool?.type === ToolType.Polyline ||
    tool?.type === ToolType.Brush;

  return {
    showCrosshair: isDrawTool,
    showBrushCursor: tool?.type === ToolType.Brush,
    showSmartPromptCursor:
      tool?.type === ToolType.InteractiveSegmenter || tool?.type === ToolType.VOS,
  };
}

/**
 * Result of keyboard dispatch logic — tells the caller what action to take.
 */
export type KeyDownAction =
  | { type: "escape-to-pan"; keepPolygonTool: boolean }
  | { type: "tool-shortcut-handled" }
  | {
      type: "forward-to-bridge";
      key: string;
      modifiers: { shift: boolean; ctrl: boolean; alt: boolean; meta: boolean };
    }
  | { type: "ignored" };

/**
 * Pure keyboard dispatch: determines what action a keydown should trigger.
 * Does NOT mutate any state — caller applies the returned action.
 */
export function classifyKeyDown(
  event: KeyboardEvent,
  tool: SelectionTool | undefined,
  interactionShape: {
    status: string;
    type?: string;
    phase?: string;
    closedPolygons?: unknown[];
  } | null,
  shortcutHandled: boolean,
): KeyDownAction {
  // Ignore when typing in inputs
  const activeElement = document.activeElement;
  if (
    activeElement instanceof HTMLInputElement ||
    activeElement instanceof HTMLTextAreaElement ||
    activeElement?.getAttribute("contenteditable") === "true"
  ) {
    return { type: "ignored" };
  }

  if (event.key === "Escape") {
    const shouldKeepPolygonTool =
      (tool?.type === ToolType.Polygon || tool?.type === ToolType.Polyline) &&
      interactionShape?.status === "creating" &&
      (interactionShape?.type === "polygon" || interactionShape?.type === "polyline") &&
      interactionShape?.phase === "drawing" &&
      (interactionShape?.closedPolygons?.length ?? 0) > 0;

    return { type: "escape-to-pan", keepPolygonTool: shouldKeepPolygonTool };
  }

  if (shortcutHandled && event.key !== "Enter") {
    return { type: "tool-shortcut-handled" };
  }

  if (
    (event.key === "Enter" || event.key === "Backspace") &&
    (tool?.type === ToolType.Rectangle ||
      tool?.type === ToolType.InteractiveSegmenter ||
      tool?.type === ToolType.VOS ||
      tool?.type === ToolType.Polygon ||
      tool?.type === ToolType.Polyline)
  ) {
    return {
      type: "forward-to-bridge",
      key: event.key,
      modifiers: {
        shift: event.shiftKey,
        ctrl: event.ctrlKey,
        alt: event.altKey,
        meta: event.metaKey,
      },
    };
  }

  return { type: "ignored" };
}
