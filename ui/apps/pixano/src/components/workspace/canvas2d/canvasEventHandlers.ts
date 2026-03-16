/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ToolType, type SelectionTool } from "$lib/tools";
import { panTool, polygonTool, polylineTool, rectangleTool } from "$lib/tools/canvasToolPolicy";

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
  return tool.type;
}

/**
 * Describes the overlay/cursor state changes needed when switching tools.
 */
export interface ToolChangeAction {
  cursor: string;
  clearCrosshair: boolean;
  clearBrushCursor: boolean;
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
      cleanupPolygonPreview: true,
    };
  }
  if (tool?.type === ToolType.Rectangle) {
    return {
      cursor: rectangleTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      cleanupPolygonPreview: true,
    };
  }
  if (tool?.type === ToolType.Polygon) {
    return {
      cursor: polygonTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      cleanupPolygonPreview: false,
    };
  }
  if (tool?.type === ToolType.Polyline) {
    return {
      cursor: polylineTool.cursor,
      clearCrosshair: false,
      clearBrushCursor: true,
      cleanupPolygonPreview: false,
    };
  }
  if (tool?.type === ToolType.Brush) {
    return {
      cursor: "none",
      clearCrosshair: true,
      clearBrushCursor: false,
      cleanupPolygonPreview: true,
    };
  }
  // Default / unknown tool
  return {
    cursor: "default",
    clearCrosshair: true,
    clearBrushCursor: true,
    cleanupPolygonPreview: true,
  };
}

/**
 * Describes the cursor overlay state changes for a pointer-move frame flush.
 */
export interface CursorFlushAction {
  showCrosshair: boolean;
  showBrushCursor: boolean;
}

/**
 * Compute which cursor overlays should be active for the current tool.
 * The actual position/state updates are done by the caller.
 */
export function computeCursorFlushAction(tool: SelectionTool | undefined): CursorFlushAction {
  const isDrawTool =
    tool?.type === ToolType.Rectangle ||
    tool?.type === ToolType.Polygon ||
    tool?.type === ToolType.Polyline ||
    tool?.type === ToolType.Brush;

  return {
    showCrosshair: isDrawTool,
    showBrushCursor: tool?.type === ToolType.Brush,
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
