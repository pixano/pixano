/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// $lib/tools — Tool finite state machines + selection types
// ============================================================

import type { Command } from "$lib/commands";
import type { Document, NodeId } from "$lib/document";

// --------------- Geometry Primitives ---------------

export interface Point2D {
  readonly x: number;
  readonly y: number;
}

export interface PolygonPoint2D extends Point2D {
  readonly id: number;
}

export interface PolygonEdgeHint extends Point2D {
  readonly shapeIndex: number;
  readonly afterIndex: number;
}

export interface LabeledClick {
  readonly point: Point2D;
  readonly label: number; // 1 = positive, 0 = negative
}

// --------------- AI Types ---------------

export interface AIRequestParams {
  readonly modelId: string;
  readonly input: unknown;
}

export interface AIResult {
  readonly requestId: string;
  readonly output: unknown;
}

// --------------- Preview ---------------

export type PreviewShape =
  | { readonly type: "rectangle"; readonly origin: Point2D; readonly current: Point2D; readonly editable?: boolean }
  | {
      readonly type: "polygon";
      readonly phase: "drawing" | "editing";
      readonly closedPolygons: readonly (readonly PolygonPoint2D[])[];
      readonly points: readonly PolygonPoint2D[];
      readonly current?: Point2D;
      readonly hoveredEdge?: PolygonEdgeHint | null;
    }
  | { readonly type: "mask"; readonly data: ImageData }
  | { readonly type: "point"; readonly position: Point2D; readonly label: number }
  | { readonly type: "keypoints"; readonly points: readonly Point2D[] }
  | { readonly type: "brush"; readonly path: readonly Point2D[]; readonly radius: number };

// --------------- Tool States ---------------

export type ToolState =
  | { readonly phase: "idle" }
  | { readonly phase: "drawing"; readonly origin: Point2D; readonly current: Point2D }
  | { readonly phase: "editingNew"; readonly origin: Point2D; readonly current: Point2D }
  | { readonly phase: "editing"; readonly shapeId: NodeId }
  | {
      readonly phase: "placingKeypoints";
      readonly points: readonly Point2D[];
      readonly current?: Point2D;
    }
  | {
      readonly phase: "drawingPolygon";
      readonly mode: "drawing" | "editing";
      readonly closedPolygons: readonly (readonly PolygonPoint2D[])[];
      readonly points: readonly PolygonPoint2D[];
      readonly current?: Point2D;
    }
  | { readonly phase: "brushing"; readonly path: readonly Point2D[] }
  | { readonly phase: "waitingForAI"; readonly requestId: string }
  | { readonly phase: "previewingAIResult"; readonly result: AIResult }
  | { readonly phase: "collectingPoints"; readonly points: readonly LabeledClick[] };

// --------------- Tool Events ---------------

export type ToolEvent =
  | { readonly type: "pointerDown"; readonly position: Point2D; readonly button: number }
  | { readonly type: "pointerMove"; readonly position: Point2D }
  | { readonly type: "pointerUp"; readonly position: Point2D }
  | {
      readonly type: "polygonMoveVertex";
      readonly polygonIndex: number;
      readonly pointId: number;
      readonly position: Point2D;
    }
  | {
      readonly type: "polygonInsertVertex";
      readonly polygonIndex: number;
      readonly afterIndex: number;
      readonly position: Point2D;
    }
  | {
      readonly type: "polygonTranslate";
      readonly delta: Point2D;
    }
  | { readonly type: "keyDown"; readonly key: string; readonly modifiers?: KeyModifiers }
  | { readonly type: "keyUp"; readonly key: string }
  | { readonly type: "cancel" }
  | { readonly type: "confirm" }
  | { readonly type: "aiResult"; readonly requestId: string; readonly result: AIResult }
  | { readonly type: "aiError"; readonly requestId: string; readonly error: string };

export interface KeyModifiers {
  readonly shift?: boolean;
  readonly ctrl?: boolean;
  readonly alt?: boolean;
  readonly meta?: boolean;
}

// --------------- Tool Side Effects ---------------

export type ToolSideEffect =
  | { readonly type: "emitCommand"; readonly command: Command }
  | { readonly type: "requestAI"; readonly requestId: string; readonly params: AIRequestParams }
  | { readonly type: "cancelAI"; readonly requestId: string }
  | { readonly type: "updatePreview"; readonly preview: PreviewShape | null }
  | { readonly type: "setCursor"; readonly cursor: string }
  | { readonly type: "beginTransaction"; readonly description: string }
  | { readonly type: "commitTransaction" }
  | { readonly type: "abortTransaction" }
  | { readonly type: "requestSave"; readonly shapeType: "bbox" | "polygon" | "mask" | "keypoints"; readonly geometry: unknown };

// --------------- Tool Transition ---------------

export interface ToolTransition {
  readonly newState: ToolState;
  readonly sideEffects: readonly ToolSideEffect[];
}

// --------------- Tool Context ---------------

/** Read-only context available to tools during transitions. */
export interface ToolContext {
  readonly document: Document;
  readonly selectedIds: ReadonlySet<NodeId>;
  readonly viewName: string;
  readonly canvasWidth: number;
  readonly canvasHeight: number;
}

// --------------- Tool FSM ---------------

/**
 * A tool is a pure finite state machine.
 *
 * Given a state and an event, it produces a new state and side effects.
 * No rendering, no DOM, no Svelte, no Konva — just state transitions.
 */
export interface ToolFSM {
  readonly id: string;
  readonly name: string;
  readonly icon: string;
  readonly defaultCursor: string;

  /** Compute the next state and side effects from a (state, event) pair. */
  transition(state: ToolState, event: ToolEvent, context: ToolContext): ToolTransition;

  /** Return the initial state for this tool. */
  getInitialState(): ToolState;
}

// --------------- Tool Registry ---------------

/** Registry for discovering and selecting tools. */
export interface ToolRegistry {
  register(tool: ToolFSM): void;
  unregister(toolId: string): void;
  get(toolId: string): ToolFSM | undefined;
  getAll(): ReadonlyArray<ToolFSM>;
}

// --------------- Selection Types ---------------

/**
 * Canonical UI tool identifiers.
 *
 * These values are persisted in stores and compared across packages.
 */
export enum ToolType {
  PointSelection = "POINT_SELECTION",
  Rectangle = "RECTANGLE",
  Polygon = "POLYGON",
  Keypoint = "KEY_POINT",
  Delete = "DELETE",
  Pan = "PAN",
  Fusion = "FUSION",
  Classification = "CLASSIFICATION",
  Brush = "BRUSH",
}

export interface ToolPostProcessor {
  reset(): void;
}

type BaseTool<T extends ToolType> = {
  name: string;
  cursor: string;
  type: T;
  isSmart?: boolean;
  postProcessor?: ToolPostProcessor;
};

export type PolygonOutputMode = "polygon" | "mask";

export type AllTool = BaseTool<
  | ToolType.Rectangle
  | ToolType.Pan
  | ToolType.Delete
  | ToolType.Classification
  | ToolType.Keypoint
  | ToolType.Fusion
>;

export type LabeledPointTool = BaseTool<ToolType.PointSelection> & {
  label: number;
};

export type PolygonSelectionTool = BaseTool<ToolType.Polygon> & {
  outputMode: PolygonOutputMode;
};

export type BrushSelectionTool = BaseTool<ToolType.Brush> & {
  mode: "draw" | "erase";
};

export type SelectionTool = AllTool | LabeledPointTool | BrushSelectionTool | PolygonSelectionTool;
