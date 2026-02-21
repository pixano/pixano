/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  Point2D,
  PolygonPoint2D,
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolSideEffect,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";
import type { PolygonOutputMode } from "$lib/types/tools";

/**
 * Polygon drawing tool.
 *
 * States: idle → drawingPolygon → idle
 *
 * Click to add points. Double-click or Enter to close/confirm.
 * Escape to cancel. Backspace to remove last point.
 * Each polygon draw is wrapped in a transaction.
 */
export class PolygonToolFSM implements ToolFSM {
  readonly id = "polygon";
  readonly name = "Polygon selection";
  readonly icon = "polygon";
  readonly defaultCursor = "crosshair";
  readonly defaultOutputMode: PolygonOutputMode;

  private static readonly MIN_POINTS = 3;
  private static readonly CLOSE_DISTANCE = 10;

  constructor(options?: { defaultOutputMode?: PolygonOutputMode }) {
    this.defaultOutputMode = options?.defaultOutputMode ?? "polygon";
  }

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, _context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          const nextState: ToolState = {
            phase: "drawingPolygon",
            mode: "drawing",
            closedPolygons: [],
            points: [this.createPoint(event.position, 0)],
            current: event.position,
          };

          return {
            newState: nextState,
            sideEffects: [
              { type: "beginTransaction", description: "Draw polygon" },
              this.previewEffect(nextState),
            ],
          };
        }
        break;

      case "drawingPolygon": {
        const currentState = state;

        if (event.type === "pointerMove") {
          const nextState: ToolState = {
            ...currentState,
            current: event.position,
          };

          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        if (event.type === "pointerDown" && event.button === 0) {
          if (currentState.mode === "editing") {
            const nextState: ToolState = {
              ...currentState,
              mode: "drawing",
              points: [this.createPoint(event.position, 0)],
              current: event.position,
            };

            return {
              newState: nextState,
              sideEffects: [this.previewEffect(nextState)],
            };
          }

          if (
            currentState.points.length >= PolygonToolFSM.MIN_POINTS &&
            this.isCloseToFirstPoint(event.position, currentState.points[0])
          ) {
            const nextState: ToolState = {
              ...currentState,
              mode: "editing",
              closedPolygons: [...currentState.closedPolygons, [...currentState.points]],
              points: [],
              current: undefined,
            };

            return {
              newState: nextState,
              sideEffects: [this.previewEffect(nextState)],
            };
          }

          const nextPointId = this.findNextPointId(currentState.points);
          const newPoints = [...currentState.points, this.createPoint(event.position, nextPointId)];
          const nextState: ToolState = {
            ...currentState,
            points: newPoints,
            current: event.position,
          };

          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        if (event.type === "polygonMoveVertex") {
          const nextState = this.moveVertex(currentState, event);
          if (!nextState) {
            return { newState: state, sideEffects: [] };
          }
          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        if (event.type === "polygonInsertVertex") {
          if (currentState.mode !== "editing") {
            return { newState: state, sideEffects: [] };
          }

          const nextState = this.insertVertex(currentState, event);
          if (!nextState) {
            return { newState: state, sideEffects: [] };
          }
          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        if (event.type === "polygonTranslate") {
          const nextState = this.translatePolygonState(currentState, event.delta);
          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
          const polygonsToSave =
            currentState.mode === "editing"
              ? [...currentState.closedPolygons]
              : currentState.points.length >= PolygonToolFSM.MIN_POINTS
                ? [...currentState.closedPolygons, [...currentState.points]]
                : [];

          if (polygonsToSave.length > 0) {
            const outputMode =
              event.type === "keyDown" && event.modifiers?.shift
                ? "mask"
                : this.defaultOutputMode;
            return this.confirmPolygon(polygonsToSave, outputMode);
          }
        }

        if (event.type === "keyDown" && event.key === "Backspace") {
          if (currentState.mode === "drawing" && currentState.points.length > 1) {
            const newPoints = currentState.points.slice(0, -1);
            const nextState: ToolState = {
              ...currentState,
              points: newPoints,
            };

            return {
              newState: nextState,
              sideEffects: [this.previewEffect(nextState)],
            };
          }

          if (currentState.mode === "drawing" && currentState.closedPolygons.length > 0) {
            const nextState: ToolState = {
              ...currentState,
              mode: "editing",
              points: [],
              current: undefined,
            };
            return {
              newState: nextState,
              sideEffects: [this.previewEffect(nextState)],
            };
          }

          if (currentState.mode === "drawing" && currentState.points.length <= 1) {
            return {
              newState: { phase: "idle" },
              sideEffects: [
                { type: "updatePreview", preview: null },
                { type: "abortTransaction" },
              ],
            };
          }
        }

        if (event.type === "cancel" || (event.type === "keyDown" && event.key === "Escape")) {
          if (currentState.mode === "drawing" && currentState.closedPolygons.length > 0) {
            const nextState: ToolState = {
              ...currentState,
              mode: "editing",
              points: [],
              current: undefined,
            };
            return {
              newState: nextState,
              sideEffects: [this.previewEffect(nextState)],
            };
          }

          return {
            newState: { phase: "idle" },
            sideEffects: [
              { type: "updatePreview", preview: null },
              { type: "abortTransaction" },
            ],
          };
        }
        break;
      }
    }

    return { newState: state, sideEffects: [] };
  }

  private confirmPolygon(
    polygons: readonly (readonly PolygonPoint2D[])[],
    outputMode: PolygonOutputMode,
  ): ToolTransition {
    const sideEffects: ToolSideEffect[] = [
      { type: "updatePreview", preview: null },
      {
        type: "requestSave",
        shapeType: "polygon",
        geometry: {
          polygons: polygons.map((polygon) =>
            polygon.map((point) => ({
              x: point.x,
              y: point.y,
              id: point.id,
            })),
          ),
          outputMode,
        },
      },
      { type: "commitTransaction" },
    ];

    return { newState: { phase: "idle" }, sideEffects };
  }

  private previewEffect(state: ToolState): ToolSideEffect {
    if (state.phase !== "drawingPolygon") {
      return { type: "updatePreview", preview: null };
    }

    return {
      type: "updatePreview",
      preview: {
        type: "polygon",
        phase: state.mode,
        closedPolygons: state.closedPolygons,
        points: state.points,
        current: state.current,
      },
    };
  }

  private createPoint(position: Point2D, id: number): PolygonPoint2D {
    return {
      x: position.x,
      y: position.y,
      id,
    };
  }

  private findNextPointId(points: readonly PolygonPoint2D[]): number {
    if (points.length === 0) return 0;
    return points.reduce((maxId, point) => Math.max(maxId, point.id), -1) + 1;
  }

  private moveVertex(
    state: Extract<ToolState, { phase: "drawingPolygon" }>,
    event: Extract<ToolEvent, { type: "polygonMoveVertex" }>,
  ): ToolState | null {
    const updatePoint = (points: readonly PolygonPoint2D[]) => {
      let changed = false;
      const nextPoints = points.map((point) => {
        if (point.id !== event.pointId) return point;
        changed = true;
        return {
          ...point,
          x: event.position.x,
          y: event.position.y,
        };
      });
      return changed ? nextPoints : null;
    };

    if (event.polygonIndex < state.closedPolygons.length) {
      const target = state.closedPolygons[event.polygonIndex];
      const updated = updatePoint(target);
      if (!updated) return null;

      const nextClosed = state.closedPolygons.map((polygon, index) =>
        index === event.polygonIndex ? updated : polygon,
      );
      return {
        ...state,
        closedPolygons: nextClosed,
      };
    }

    if (state.mode === "drawing" && event.polygonIndex === state.closedPolygons.length) {
      const updated = updatePoint(state.points);
      if (!updated) return null;
      return {
        ...state,
        points: updated,
      };
    }

    return null;
  }

  private insertVertex(
    state: Extract<ToolState, { phase: "drawingPolygon" }>,
    event: Extract<ToolEvent, { type: "polygonInsertVertex" }>,
  ): ToolState | null {
    const target = state.closedPolygons[event.polygonIndex];
    if (!target || target.length < 2) return null;
    if (event.afterIndex < 0 || event.afterIndex >= target.length) return null;

    const newPoint: PolygonPoint2D = this.createPoint(
      {
        x: event.position.x,
        y: event.position.y,
      },
      this.findNextPointId(target),
    );

    const updatedPolygon = [...target];
    updatedPolygon.splice(event.afterIndex + 1, 0, newPoint);

    return {
      ...state,
      closedPolygons: state.closedPolygons.map((polygon, index) =>
        index === event.polygonIndex ? updatedPolygon : polygon,
      ),
    };
  }

  private isCloseToFirstPoint(point: Point2D, first: Point2D): boolean {
    const dx = point.x - first.x;
    const dy = point.y - first.y;
    return Math.sqrt(dx * dx + dy * dy) < PolygonToolFSM.CLOSE_DISTANCE;
  }

  private translatePolygonState(
    state: Extract<ToolState, { phase: "drawingPolygon" }>,
    delta: Point2D,
  ): ToolState {
    if (delta.x === 0 && delta.y === 0) {
      return state;
    }

    const translatePoint = (point: PolygonPoint2D): PolygonPoint2D => ({
      ...point,
      x: point.x + delta.x,
      y: point.y + delta.y,
    });

    return {
      ...state,
      closedPolygons: state.closedPolygons.map((polygon) => polygon.map(translatePoint)),
      points: state.points.map(translatePoint),
      current: state.current
        ? {
            x: state.current.x + delta.x,
            y: state.current.y + delta.y,
          }
        : undefined,
    };
  }
}
