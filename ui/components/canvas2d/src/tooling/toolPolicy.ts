/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  ToolType,
  brushDrawTool,
  brushEraseTool,
  panTool,
  polygonTool,
  rectangleTool,
  type BrushSelectionTool,
  type SelectionTool,
} from "@pixano/tools";

export function isSupportedCanvasTool(tool: SelectionTool | undefined): boolean {
  if (!tool) return false;
  return (
    tool.type === ToolType.Pan ||
    (tool.type === ToolType.Rectangle && !tool.isSmart) ||
    tool.type === ToolType.Polygon ||
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
  selectPolygon(): void;
  selectBrushDraw(): void;
  toggleBrushMode(): void;
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

  if (event.key === "r" || event.key === "R") {
    actions.selectRectangle();
    return true;
  }

  if (event.key === "p" || event.key === "P") {
    actions.selectPolygon();
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

export { brushDrawTool, brushEraseTool, panTool, polygonTool, rectangleTool };
