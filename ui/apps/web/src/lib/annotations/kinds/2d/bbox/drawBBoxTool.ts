/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Square } from "lucide-svelte";

import { commitNewAnnotation } from "$lib/annotations/payloadBuilders.js";
import {
  BBOX_COLOR_DRAFT,
  getPixelFrame,
  PIXEL_THRESHOLD,
  pixelToNormalized,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import {
  DEFAULT_TOOL_2D,
  type Tool2D,
  type ToolHandler2D,
} from "$lib/annotations/scene/tool.js";

/**
 * Rubber-band bbox drawing. Pointer down anchors a corner, move stretches
 * the preview rectangle, up clamps it to the image frame and commits the
 * (entity, bbox) create pair. Hands control back to the select tool when
 * done or cancelled.
 */
class DrawBBoxHandler implements ToolHandler2D {
  private draftRect: Konva.Rect | null = null;
  private draftOrigin: { x: number; y: number } | null = null;

  constructor(private readonly ctx: Scene2DContext) {}

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return;
    this.draftOrigin = pos;
    this.draftRect = new Konva.Rect({
      x: pos.x,
      y: pos.y,
      width: 0,
      height: 0,
      stroke: BBOX_COLOR_DRAFT,
      strokeWidth: 2,
      dash: [6, 4],
      listening: false,
    });
    this.ctx.annotationLayer.add(this.draftRect);
    this.ctx.annotationLayer.batchDraw();
  }

  onPointerMove(): void {
    if (!this.draftRect || !this.draftOrigin) return;
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return;
    this.draftRect.position({
      x: Math.min(pos.x, this.draftOrigin.x),
      y: Math.min(pos.y, this.draftOrigin.y),
    });
    this.draftRect.width(Math.abs(pos.x - this.draftOrigin.x));
    this.draftRect.height(Math.abs(pos.y - this.draftOrigin.y));
    this.ctx.annotationLayer.batchDraw();
  }

  onPointerUp(): void {
    if (!this.draftRect || !this.draftOrigin) return;

    const rectX = this.draftRect.x();
    const rectY = this.draftRect.y();
    const width = this.draftRect.width();
    const height = this.draftRect.height();
    this._destroyDraft();

    if (width < PIXEL_THRESHOLD || height < PIXEL_THRESHOLD) {
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return;
    }

    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) {
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return;
    }

    const clampedLeft = Math.max(frame.x, rectX);
    const clampedTop = Math.max(frame.y, rectY);
    const clampedW = Math.min(frame.x + frame.w, rectX + width) - clampedLeft;
    const clampedH = Math.min(frame.y + frame.h, rectY + height) - clampedTop;

    if (clampedW < PIXEL_THRESHOLD || clampedH < PIXEL_THRESHOLD) {
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return;
    }

    const coordsNorm = pixelToNormalized(clampedLeft, clampedTop, clampedW, clampedH, frame);

    const bbox = commitNewAnnotation(this.ctx, "bbox", coordsNorm);

    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(bbox.id);
    this.ctx.requestRedraw();
  }

  onKeyDown(event: KeyboardEvent): boolean {
    if (event.key === "Escape") {
      this._destroyDraft();
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return true;
    }
    return false;
  }

  deactivate(): void {
    this._destroyDraft();
  }

  private _destroyDraft(): void {
    if (this.draftRect) {
      this.draftRect.destroy();
      this.ctx.annotationLayer.batchDraw();
    }
    this.draftRect = null;
    this.draftOrigin = null;
  }
}

export const drawBBoxTool: Tool2D = {
  id: "draw-bbox",
  label: "Add box annotation (R)",
  icon: Square,
  kind: "bbox",
  cursor: "crosshair",
  createHandler: (ctx: Scene2DContext) => new DrawBBoxHandler(ctx),
};
