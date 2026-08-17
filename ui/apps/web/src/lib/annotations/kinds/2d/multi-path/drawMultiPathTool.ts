/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Pentagon, PenTool } from "lucide-svelte";

import { fromNormalizedSubPaths } from "./multiPathGeometry.js";
import {
  DRAW_POLYGON_TOOL_ID,
  DRAW_POLYLINE_TOOL_ID,
  minPointsFor,
  type MultiPathGeometry,
} from "./multiPathTypes.js";
import type { LocalMultiPath } from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import { commitDraftWithEntity } from "$lib/annotations/payloadBuilders.js";
import {
  BBOX_COLOR_DRAFT,
  getPixelFrame,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { DEFAULT_TOOL_2D, type Tool2D, type ToolHandler2D } from "$lib/annotations/scene/tool.js";

const PREVIEW_STROKE_WIDTH = 2;
const PREVIEW_VERTEX_RADIUS = 3;
const HINT_FONT_SIZE = 12;
const HINT_OFFSET = 14;
/** The segment from the last placed point to the cursor, shown while drawing. */
const RUBBER_DASH = [4, 4];

/** A point in normalized [0,1] image space. */
interface NormPoint {
  x: number;
  y: number;
}

/**
 * Click-per-vertex path drawing, shared by the polygon and polyline tools:
 * they differ only by `isClosed`, which is a field of the geometry rather than
 * a different kind — the backend's `MultiPath` makes the same choice.
 *
 * Sub-paths are first-class: `N` finishes the current one and starts another,
 * so a single annotation can hold several rings or several strokes (the legacy
 * UI bound the same key to the same idea). `Enter` finishes the whole thing.
 *
 * Keyboard: `Enter` commits, `N` starts a new sub-path, `Backspace` undoes the
 * last point, `Escape` cancels.
 */
class DrawMultiPathHandler implements ToolHandler2D {
  /** Completed sub-paths, plus the one being drawn as the last entry. */
  private subPaths: NormPoint[][] = [[]];
  private preview: Konva.Group | null = null;

  constructor(
    private readonly ctx: Scene2DContext,
    private readonly isClosed: boolean,
  ) {}

  activate(): void {
    this._reset();
  }

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;
    const frame = this._frame();
    if (!frame) return;
    const point = this._toNormalized(frame);
    if (!point) return;
    this._current().push(point);
    this._refreshPreview();
  }

  onPointerMove(): void {
    // Redraw so the rubber-band segment and the hint follow the cursor.
    this._refreshPreview();
  }

  onKeyDown(event: KeyboardEvent): boolean {
    switch (event.key) {
      case "Escape":
        this._reset();
        this.ctx.setActiveTool(DEFAULT_TOOL_2D);
        return true;
      case "Enter":
        this._commit();
        return true;
      case "n":
      case "N":
        this._startSubPath();
        return true;
      case "Backspace":
        this._undo();
        this._refreshPreview();
        return true;
      default:
        return false;
    }
  }

  deactivate(): void {
    this._reset();
  }

  // ─── Sub-paths ────────────────────────────────────────────────────────────

  private _current(): NormPoint[] {
    return this.subPaths[this.subPaths.length - 1];
  }

  /**
   * Close the current sub-path and open a new one. Refused while the current
   * one is too short to exist — otherwise the commit would silently drop it and
   * the points the user placed would vanish without explanation.
   */
  private _startSubPath(): void {
    if (this._current().length < minPointsFor(this.isClosed)) return;
    this.subPaths.push([]);
    this._refreshPreview();
  }

  /** Remove the last point, stepping back into the previous sub-path if empty. */
  private _undo(): void {
    if (this._current().length > 0) {
      this._current().pop();
      return;
    }
    if (this.subPaths.length > 1) {
      this.subPaths.pop();
      this._current().pop();
    }
  }

  // ─── Geometry ─────────────────────────────────────────────────────────────

  private _frame(): PixelFrame | null {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return null;
    return frame;
  }

  /**
   * Stage pointer → normalized image space, clamped to [0,1]: the backend
   * rejects coordinates outside that range outright.
   */
  private _toNormalized(frame: PixelFrame): NormPoint | null {
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return null;
    return {
      x: Math.min(1, Math.max(0, (pos.x - frame.x) / frame.w)),
      y: Math.min(1, Math.max(0, (pos.y - frame.y) / frame.h)),
    };
  }

  private _toPixels(points: readonly NormPoint[], frame: PixelFrame): number[] {
    const flat: number[] = [];
    for (const point of points) {
      flat.push(frame.x + point.x * frame.w, frame.y + point.y * frame.h);
    }
    return flat;
  }

  // ─── Preview ──────────────────────────────────────────────────────────────

  private _refreshPreview(): void {
    this.preview?.destroy();
    this.preview = null;

    const frame = this._frame();
    if (!frame) return;

    const group = new Konva.Group({ listening: false });
    const lastIndex = this.subPaths.length - 1;

    for (const [index, points] of this.subPaths.entries()) {
      if (points.length === 0) continue;
      const pixels = this._toPixels(points, frame);
      // Only finished sub-paths are drawn closed; the one in progress stays
      // open so the shape reads as unfinished.
      group.add(
        new Konva.Line({
          points: pixels,
          stroke: BBOX_COLOR_DRAFT,
          strokeWidth: PREVIEW_STROKE_WIDTH,
          closed: this.isClosed && index < lastIndex,
        }),
      );
      for (let i = 0; i + 1 < pixels.length; i += 2) {
        group.add(
          new Konva.Circle({
            x: pixels[i],
            y: pixels[i + 1],
            radius: PREVIEW_VERTEX_RADIUS,
            fill: BBOX_COLOR_DRAFT,
          }),
        );
      }
    }

    const pos = this.ctx.stage.getPointerPosition();
    const current = this._current();
    if (pos && current.length > 0) {
      const last = this._toPixels([current[current.length - 1]], frame);
      group.add(
        new Konva.Line({
          points: [last[0], last[1], pos.x, pos.y],
          stroke: BBOX_COLOR_DRAFT,
          strokeWidth: PREVIEW_STROKE_WIDTH,
          dash: RUBBER_DASH,
        }),
      );
    }

    if (pos) {
      group.add(
        new Konva.Text({
          x: pos.x + HINT_OFFSET,
          y: pos.y - HINT_OFFSET,
          text: this._hintText(),
          fontSize: HINT_FONT_SIZE,
          fontFamily: "system-ui, sans-serif",
          fill: BBOX_COLOR_DRAFT,
        }),
      );
    }

    this.ctx.annotationLayer.add(group);
    this.preview = group;
    this.ctx.annotationLayer.batchDraw();
  }

  /** Tell the user how far off a committable shape they are. */
  private _hintText(): string {
    const shape = this.isClosed ? "Polygon" : "Polyline";
    const placed = this._current().length;
    const missing = minPointsFor(this.isClosed) - placed;
    if (missing > 0) return `${shape}: ${missing} more point${missing > 1 ? "s" : ""}`;
    const parts = this.subPaths.filter((p) => p.length > 0).length;
    const suffix = parts > 1 ? ` (${parts} parts)` : "";
    return `${shape}: Enter to finish, N for a new part${suffix}`;
  }

  // ─── Commit ───────────────────────────────────────────────────────────────

  /**
   * Keep only sub-paths long enough to exist, then commit if anything is left.
   * A too-short trailing sub-path is dropped rather than rejected: it is the
   * common case of pressing Enter right after starting a new part.
   */
  private _commit(): void {
    const minPoints = minPointsFor(this.isClosed);
    const usable = this.subPaths.filter((points) => points.length >= minPoints);
    if (usable.length === 0) return;

    const geometry: MultiPathGeometry = fromNormalizedSubPaths(usable, this.isClosed);
    this._reset();

    const path: LocalMultiPath = {
      id: generateShortId(),
      entityId: "",
      kind: "multi_path",
      viewId: this.ctx.buildContext.viewId,
      geometry,
      persisted: false,
    };
    this.ctx.collection.add(path);
    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(path.id);
    this.ctx.requestRedraw();

    this.ctx.beginPendingAnnotation({
      label: this.isClosed ? "polygon" : "polyline",
      onConfirm: (choice) => commitDraftWithEntity(path, choice, this.ctx),
      onCancel: () => this._discardDraft(path.id),
    });
  }

  private _discardDraft(localId: string): void {
    this.ctx.collection.remove(localId);
    this.ctx.requestRedraw();
  }

  private _reset(): void {
    this.preview?.destroy();
    this.preview = null;
    this.subPaths = [[]];
    this.ctx.annotationLayer.batchDraw();
  }
}

export const drawPolygonTool: Tool2D = {
  id: DRAW_POLYGON_TOOL_ID,
  label: "Draw polygon (P)",
  icon: Pentagon,
  kind: "multi_path",
  cursor: "crosshair",
  createHandler: (ctx: Scene2DContext) => new DrawMultiPathHandler(ctx, true),
};

export const drawPolylineTool: Tool2D = {
  id: DRAW_POLYLINE_TOOL_ID,
  label: "Draw polyline (L)",
  icon: PenTool,
  kind: "multi_path",
  cursor: "crosshair",
  createHandler: (ctx: Scene2DContext) => new DrawMultiPathHandler(ctx, false),
};
