/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  Point2D,
  IndexedPoint2D,
  ToolContext,
  ToolEvent,
  ToolFSM,
  ToolSideEffect,
  ToolState,
  ToolTransition,
} from "$lib/types/tools";

/**
 * Polyline (multi-linestring) drawing tool.
 *
 * States: idle -> drawingPolyline -> idle
 *
 * Click to add points. Press N to finish the current sub-path and
 * start a new disconnected one (like tracklet "N" in video mode).
 * Enter to confirm and save all sub-paths. Escape to cancel.
 * Backspace to undo last point.
 *
 * Each polyline draw is wrapped in a transaction.
 * Minimum 2 points per sub-path.
 */
export class PolylineToolFSM implements ToolFSM {
  readonly id = "polyline";
  readonly name = "Polyline selection";
  readonly icon = "polyline";
  readonly defaultCursor = "crosshair";

  private static readonly MIN_POINTS = 2;

  getInitialState(): ToolState {
    return { phase: "idle" };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  transition(state: ToolState, event: ToolEvent, _context: ToolContext): ToolTransition {
    switch (state.phase) {
      case "idle":
        if (event.type === "pointerDown" && event.button === 0) {
          const nextState: ToolState = {
            phase: "drawingPolyline",
            mode: "drawing",
            closedPolygons: [],
            points: [this.createPoint(event.position, 0)],
            current: event.position,
          };

          return {
            newState: nextState,
            sideEffects: [
              { type: "beginTransaction", description: "Draw polyline" },
              this.previewEffect(nextState),
            ],
          };
        }
        break;

      case "drawingPolyline": {
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
            // Start a new sub-path from editing mode
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

          // Add a new point
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
          const nextState = this.translatePolylineState(currentState, event.delta);
          return {
            newState: nextState,
            sideEffects: [this.previewEffect(nextState)],
          };
        }

        // N key: finish current sub-path and get ready for a new one
        if (event.type === "keyDown" && (event.key === "n" || event.key === "N")) {
          if (
            currentState.mode === "drawing" &&
            currentState.points.length >= PolylineToolFSM.MIN_POINTS
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
          // Not enough points — ignore
          return { newState: state, sideEffects: [] };
        }

        if (event.type === "confirm" || (event.type === "keyDown" && event.key === "Enter")) {
          const pathsToSave =
            currentState.mode === "editing"
              ? [...currentState.closedPolygons]
              : currentState.points.length >= PolylineToolFSM.MIN_POINTS
                ? [...currentState.closedPolygons, [...currentState.points]]
                : [];

          if (pathsToSave.length > 0) {
            return this.confirmPolyline(pathsToSave);
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

  private confirmPolyline(
    paths: readonly (readonly IndexedPoint2D[])[],
  ): ToolTransition {
    const sideEffects: ToolSideEffect[] = [
      { type: "updatePreview", preview: null },
      {
        type: "requestSave",
        shapeType: "polyline",
        geometry: {
          polygons: paths.map((path) =>
            path.map((point) => ({
              x: point.x,
              y: point.y,
              id: point.id,
            })),
          ),
        },
      },
      { type: "commitTransaction" },
    ];

    return { newState: { phase: "idle" }, sideEffects };
  }

  private previewEffect(state: ToolState): ToolSideEffect {
    if (state.phase !== "drawingPolyline") {
      return { type: "updatePreview", preview: null };
    }

    return {
      type: "updatePreview",
      preview: {
        type: "polyline",
        phase: state.mode,
        closedPolygons: state.closedPolygons,
        points: state.points,
        current: state.current,
      },
    };
  }

  private createPoint(position: Point2D, id: number): IndexedPoint2D {
    return {
      x: position.x,
      y: position.y,
      id,
    };
  }

  private findNextPointId(points: readonly IndexedPoint2D[]): number {
    if (points.length === 0) return 0;
    return points.reduce((maxId, point) => Math.max(maxId, point.id), -1) + 1;
  }

  private moveVertex(
    state: Extract<ToolState, { phase: "drawingPolyline" }>,
    event: Extract<ToolEvent, { type: "polygonMoveVertex" }>,
  ): ToolState | null {
    const updatePoint = (points: readonly IndexedPoint2D[]) => {
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
    state: Extract<ToolState, { phase: "drawingPolyline" }>,
    event: Extract<ToolEvent, { type: "polygonInsertVertex" }>,
  ): ToolState | null {
    const target = state.closedPolygons[event.polygonIndex];
    if (!target || target.length < 2) return null;
    if (event.afterIndex < 0 || event.afterIndex >= target.length) return null;

    const newPoint: IndexedPoint2D = this.createPoint(
      {
        x: event.position.x,
        y: event.position.y,
      },
      this.findNextPointId(target),
    );

    const updatedPath = [...target];
    updatedPath.splice(event.afterIndex + 1, 0, newPoint);

    return {
      ...state,
      closedPolygons: state.closedPolygons.map((path, index) =>
        index === event.polygonIndex ? updatedPath : path,
      ),
    };
  }

  private translatePolylineState(
    state: Extract<ToolState, { phase: "drawingPolyline" }>,
    delta: Point2D,
  ): ToolState {
    if (delta.x === 0 && delta.y === 0) {
      return state;
    }

    const translatePoint = (point: IndexedPoint2D): IndexedPoint2D => ({
      ...point,
      x: point.x + delta.x,
      y: point.y + delta.y,
    });

    return {
      ...state,
      closedPolygons: state.closedPolygons.map((path) => path.map(translatePoint)),
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
