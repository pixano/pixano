/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Brush } from "lucide-svelte";

import { createMaskCanvas, encodeMask, tintMask, type MaskCanvas } from "./maskRaster.js";
import { DRAW_MASK_TOOL_ID, type MaskGeometry } from "./maskTypes.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import { commitDraftWithEntity } from "$lib/annotations/payloadBuilders.js";
import {
  BBOX_COLOR_DRAFT,
  getPixelFrame,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { DEFAULT_TOOL_2D, type Tool2D, type ToolHandler2D } from "$lib/annotations/scene/tool.js";

/** Brush width in *display* pixels, so the stroke feels the same at any zoom. */
const DEFAULT_BRUSH_RADIUS = 12;
const MIN_BRUSH_RADIUS = 1;
const MAX_BRUSH_RADIUS = 200;
const BRUSH_RADIUS_STEP = 2;

/** Same translucency the renderer uses, so the preview matches the result. */
const PREVIEW_OPACITY = 0.45;

/**
 * Brush cursor colours, carried over from the legacy UI's `BrushCursor.svelte`:
 * green adds, red removes. The circle is the only thing showing the brush's
 * actual size before you commit to a stroke, so the tool hides the OS cursor
 * (`cursor: "none"`) and draws this instead.
 */
const CURSOR_STROKE = { draw: "rgba(0, 200, 0, 0.7)", erase: "rgba(200, 0, 0, 0.7)" } as const;
const CURSOR_FILL = { draw: "rgba(0, 200, 0, 0.1)", erase: "rgba(200, 0, 0, 0.1)" } as const;

/** A point in the mask's own pixel grid. */
interface GridPoint {
  x: number;
  y: number;
}

/**
 * Freehand mask painting. Pointer down starts a stroke on an offscreen raster
 * sized to the image grid, move extends it, up encodes the raster to RLE and
 * commits the (entity, mask) create pair.
 *
 * The raster — not the pointer path — is the source of truth: that is what
 * makes erasing a plain `destination-out` stroke rather than a second geometry
 * to reconcile, and it is what `encodeMask` reads back at the end.
 *
 * Keyboard: `X` toggles draw/erase, `[` / `]` resize the brush, `Enter` commits,
 * `Escape` cancels. These live on the handler rather than in a settings panel so
 * the tool is usable before the panel exists (the legacy UI's `BrushSettings`
 * is the eventual home for radius, lazy-radius and friction).
 */
class DrawMaskHandler implements ToolHandler2D {
  private canvas: MaskCanvas | null = null;
  private preview: Konva.Image | null = null;
  private cursor: Konva.Circle | null = null;
  private lastPoint: GridPoint | null = null;
  private painting = false;
  private dirty = false;
  private erasing = false;
  private radius = DEFAULT_BRUSH_RADIUS;

  constructor(private readonly ctx: Scene2DContext) {}

  activate(): void {
    this._reset();
  }

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;
    const frame = this._frame();
    if (!frame) return;
    if (!this.canvas) {
      this.canvas = createMaskCanvas(this._gridSize());
      if (!this.canvas) return;
    }
    this.painting = true;
    const point = this._toGrid(frame);
    if (!point) return;
    this._paintSegment(point, point, frame);
    this.lastPoint = point;
    this._refreshPreview(frame);
    // Keep the outline on top of the stroke it just laid down.
    this._refreshCursor();
  }

  onPointerMove(): void {
    // The cursor tracks the pointer whether or not a stroke is in progress —
    // seeing the brush size *before* committing to a stroke is the point of it.
    this._refreshCursor();
    if (!this.painting || !this.canvas) return;
    const frame = this._frame();
    if (!frame) return;
    const point = this._toGrid(frame);
    if (!point) return;
    this._paintSegment(this.lastPoint ?? point, point, frame);
    this.lastPoint = point;
    this._refreshPreview(frame);
  }

  onPointerUp(): void {
    this.painting = false;
    this.lastPoint = null;
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
      case "x":
      case "X":
        this.erasing = !this.erasing;
        this._refreshCursor();
        return true;
      case "[":
        this.radius = Math.max(MIN_BRUSH_RADIUS, this.radius - BRUSH_RADIUS_STEP);
        this._refreshCursor();
        return true;
      case "]":
        this.radius = Math.min(MAX_BRUSH_RADIUS, this.radius + BRUSH_RADIUS_STEP);
        this._refreshCursor();
        return true;
      default:
        return false;
    }
  }

  deactivate(): void {
    this._reset();
    // The cursor outlives a stroke (it tracks the pointer between strokes) so
    // it is torn down here rather than in `_reset`, which runs on every commit.
    this._destroyCursor();
  }

  // ─── Painting ─────────────────────────────────────────────────────────────

  /** The mask grid: the media's own pixel dimensions, not the displayed size. */
  private _gridSize(): [number, number] {
    return [this.ctx.camera.imageHeight, this.ctx.camera.imageWidth];
  }

  private _frame(): PixelFrame | null {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return null;
    const [height, width] = this._gridSize();
    if (height <= 0 || width <= 0) return null;
    return frame;
  }

  /** Stage pointer position → the mask's pixel grid. */
  private _toGrid(frame: PixelFrame): GridPoint | null {
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return null;
    const [height, width] = this._gridSize();
    return {
      x: ((pos.x - frame.x) / frame.w) * width,
      y: ((pos.y - frame.y) / frame.h) * height,
    };
  }

  /**
   * Stroke one segment. Round caps and joins make a dragged path a continuous
   * band instead of a string of discs, and a zero-length segment (the initial
   * click) still deposits a dot.
   */
  private _paintSegment(from: GridPoint, to: GridPoint, frame: PixelFrame): void {
    const canvas = this.canvas;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    // The radius is expressed in display pixels; convert once per segment.
    const gridRadius = (this.radius * this._gridSize()[1]) / frame.w;

    context.globalCompositeOperation = this.erasing ? "destination-out" : "source-over";
    context.strokeStyle = "#ffffff";
    context.fillStyle = "#ffffff";
    context.lineWidth = gridRadius * 2;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
    context.beginPath();
    context.arc(to.x, to.y, gridRadius, 0, Math.PI * 2);
    context.fill();

    this.dirty = true;
  }

  // ─── Cursor ───────────────────────────────────────────────────────────────

  /**
   * Draw the brush outline at the pointer, sized in display pixels so it shows
   * the stroke you are about to lay down. Ported from the legacy UI's
   * `BrushCursor.svelte`; kept inside the tool because it is transient tool UI,
   * not an annotation the renderer should know about.
   */
  private _refreshCursor(): void {
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) {
      this._hideCursor();
      return;
    }
    const mode = this.erasing ? "erase" : "draw";
    if (!this.cursor) {
      this.cursor = new Konva.Circle({ listening: false });
      this.ctx.annotationLayer.add(this.cursor);
    }
    this.cursor.position(pos);
    this.cursor.radius(this.radius);
    this.cursor.stroke(CURSOR_STROKE[mode]);
    this.cursor.fill(CURSOR_FILL[mode]);
    this.cursor.visible(true);
    this.ctx.annotationLayer.batchDraw();
  }

  private _hideCursor(): void {
    this.cursor?.visible(false);
  }

  private _destroyCursor(): void {
    this.cursor?.destroy();
    this.cursor = null;
  }

  // ─── Preview ──────────────────────────────────────────────────────────────

  private _refreshPreview(frame: PixelFrame): void {
    if (!this.canvas) return;
    const tinted = tintMask(this.canvas, BBOX_COLOR_DRAFT, PREVIEW_OPACITY);
    if (!tinted) return;

    if (!this.preview) {
      this.preview = new Konva.Image({ image: undefined, listening: false });
      this.ctx.annotationLayer.add(this.preview);
    }
    this.preview.image(tinted as unknown as CanvasImageSource);
    this.preview.position({ x: frame.x, y: frame.y });
    this.preview.scale({ x: frame.w / tinted.width, y: frame.h / tinted.height });
    this.ctx.annotationLayer.batchDraw();
  }

  // ─── Commit ───────────────────────────────────────────────────────────────

  /**
   * Encode what was painted and hand it to the shared draft flow. An empty
   * raster commits nothing — erasing everything you drew cancels the gesture
   * rather than creating a mask the backend would store as its empty sentinel.
   */
  private _commit(): void {
    const geometry = this._encode();
    this._reset();
    if (!geometry) {
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return;
    }

    const mask: LocalMask = {
      id: generateShortId(),
      entityId: "",
      kind: "mask",
      viewId: this.ctx.buildContext.viewId,
      geometry,
      persisted: false,
    };
    this.ctx.collection.add(mask);
    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(mask.id);
    this.ctx.requestRedraw();

    this.ctx.beginPendingAnnotation({
      label: "mask",
      onConfirm: (choice) => commitDraftWithEntity(mask, choice, this.ctx),
      onCancel: () => this._discardDraft(mask.id),
    });
  }

  private _encode(): MaskGeometry | null {
    if (!this.canvas || !this.dirty) return null;
    return encodeMask(this.canvas);
  }

  private _discardDraft(localId: string): void {
    this.ctx.collection.remove(localId);
    this.ctx.requestRedraw();
  }

  private _reset(): void {
    if (this.preview) {
      this.preview.destroy();
      this.ctx.annotationLayer.batchDraw();
    }
    this.preview = null;
    this.canvas = null;
    this.lastPoint = null;
    this.painting = false;
    this.dirty = false;
  }
}

export const drawMaskTool: Tool2D = {
  id: DRAW_MASK_TOOL_ID,
  label: "Paint mask annotation (B)",
  icon: Brush,
  kind: "mask",
  // The brush outline *is* the cursor — showing the OS one on top would fight it.
  cursor: "none",
  createHandler: (ctx: Scene2DContext) => new DrawMaskHandler(ctx),
};
