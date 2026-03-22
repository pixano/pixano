/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  brushDrawTool,
  brushEraseTool,
  interactiveSegmenterTool,
  vosTool,
  panTool,
  polygonTool,
  polylineTool,
  rectangleTool,
  ToolType,
  type BrushSelectionTool,
  type SelectionTool,
} from "$lib/tools";

export function isSupportedCanvasTool(tool: SelectionTool | undefined): boolean {
  if (!tool) return false;
  return (
    tool.type === ToolType.Pan ||
    (tool.type === ToolType.Rectangle && !tool.isSmart) ||
    tool.type === ToolType.InteractiveSegmenter ||
    tool.type === ToolType.VOS ||
    tool.type === ToolType.Polygon ||
    tool.type === ToolType.Polyline ||
    tool.type === ToolType.Brush
  );
}

export function getFallbackCanvasTool(): SelectionTool {
  return panTool;
}

export function toggleBrushMode(tool: BrushSelectionTool): BrushSelectionTool {
  return tool.mode === "draw" ? brushEraseTool : brushDrawTool;
}

export interface ShortcutToolActions {
  selectPan(): void;
  selectRectangle(): void;
  selectInteractiveSegmenter(): void;
  selectPolygon(): void;
  selectPolyline(): void;
  selectBrushDraw(): void;
  toggleBrushMode(): void;
  toggleInteractivePromptMode(): void;
  setInteractiveBoxPrompt(): void;
  adjustBrushRadius(delta: number): void;
  saveBrushMask(): void;
}

export function handleToolShortcuts(
  event: KeyboardEvent,
  selectedTool: SelectionTool | undefined,
  actions: ShortcutToolActions,
): boolean {
  if (event.key === "Escape") {
    actions.selectPan();
    return true;
  }

  if (event.key === "w" || event.key === "W") {
    actions.selectInteractiveSegmenter();
    return true;
  }

  if (event.key === "r" || event.key === "R") {
    if (selectedTool?.type === ToolType.InteractiveSegmenter || selectedTool?.type === ToolType.VOS) {
      actions.setInteractiveBoxPrompt();
      return true;
    }
    actions.selectRectangle();
    return true;
  }

  if (event.key === "p" || event.key === "P") {
    actions.selectPolygon();
    return true;
  }

  if (event.key === "l" || event.key === "L") {
    actions.selectPolyline();
    return true;
  }

  if (event.key === "b" || event.key === "B") {
    actions.selectBrushDraw();
    return true;
  }

  if (event.key === "x" || event.key === "X") {
    if (selectedTool?.type === ToolType.Brush) {
      actions.toggleBrushMode();
      return true;
    }
    if (selectedTool?.type === ToolType.InteractiveSegmenter || selectedTool?.type === ToolType.VOS) {
      actions.toggleInteractivePromptMode();
      return true;
    }
    return false;
  }

  if (event.key === "q" || event.key === "Q") {
    if (selectedTool?.type === ToolType.Brush) {
      actions.adjustBrushRadius(-5);
      return true;
    }
    return false;
  }

  if (event.key === "e" || event.key === "E") {
    if (selectedTool?.type === ToolType.Brush) {
      actions.adjustBrushRadius(5);
      return true;
    }
    return false;
  }

  if (
    (event.key === "Enter" || event.key === "s" || event.key === "S") &&
    selectedTool?.type === ToolType.Brush
  ) {
    actions.saveBrushMask();
    return true;
  }

  return false;
}

export {
  brushDrawTool,
  brushEraseTool,
  interactiveSegmenterTool,
  vosTool,
  panTool,
  polygonTool,
  polylineTool,
  rectangleTool,
};
