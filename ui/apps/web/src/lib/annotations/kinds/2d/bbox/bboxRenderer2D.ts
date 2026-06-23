/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import type { LocalBBox } from "$lib/annotations/annotationCollection.svelte.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  normalizedToPixel,
  pixelToNormalized,
  type PixelFrame,
} from "$lib/annotations/tools/scene2dGeometry.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
  Scene2DContext,
} from "$lib/annotations/tools/types2d.js";
import { pickEntityLabel } from "$lib/annotations/types.js";

import { bboxPayloadBuilder } from "./bboxPayloadBuilder.js";

/**
 * Renders the "bbox" kind on the Konva scene: one rect (+ optional entity
 * label) per annotation, a shared transformer for the selection, and the
 * drag/transform handlers that write geometry changes back through the
 * collection and the mutation queue.
 */
class BBoxRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox" as const;

  private readonly rectByBBoxId = new Map<string, Konva.Rect>();
  private readonly labelByBBoxId = new Map<string, Konva.Label>();
  private readonly transformer: Konva.Transformer;

  constructor(private readonly ctx: Scene2DContext) {
    this.transformer = new Konva.Transformer({
      rotateEnabled: false,
      anchorStroke: BBOX_COLOR_PERSISTED,
      anchorFill: "#0f172a",
      borderStroke: BBOX_COLOR_PERSISTED,
      keepRatio: false,
      ignoreStroke: true,
    });
    ctx.annotationLayer.add(this.transformer);
  }

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const bbox of this.ctx.collection.byKind("bbox")) {
      // Entity-driven visibility: a persisted box whose entity is hidden gets
      // no node, so it is invisible AND non-clickable/non-editable. Drafts
      // (still being created) are always shown.
      if (bbox.persisted && !this.ctx.isEntityVisible(bbox.entityId)) continue;
      activeIds.add(bbox.id);
      let rect = this.rectByBBoxId.get(bbox.id);
      if (!rect) {
        const newRect = this._makeRect(bbox, frame);
        if (!newRect) continue;
        this.ctx.annotationLayer.add(newRect);
        this.rectByBBoxId.set(bbox.id, newRect);
        rect = newRect;
      } else if (frame) {
        const pixel = normalizedToPixel(bbox.geometry, frame);
        rect.position({ x: pixel.x, y: pixel.y });
        rect.width(pixel.width);
        rect.height(pixel.height);
        rect.stroke(bbox.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT);
        rect.dash(bbox.persisted ? [] : [6, 4]);
      }

      let label = this.labelByBBoxId.get(bbox.id);
      if (!label) {
        label = this._makeLabel(bbox.persisted, bbox.entity) ?? undefined;
        if (label) {
          this.ctx.annotationLayer.add(label);
          this.labelByBBoxId.set(bbox.id, label);
        }
      }
      if (label) this._positionLabel(label, rect);
    }

    for (const [id, rect] of this.rectByBBoxId) {
      if (!activeIds.has(id)) { rect.destroy(); this.rectByBBoxId.delete(id); }
    }
    for (const [id, label] of this.labelByBBoxId) {
      if (!activeIds.has(id)) { label.destroy(); this.labelByBBoxId.delete(id); }
    }

    this._syncTransformer();
    this.ctx.annotationLayer.batchDraw();
  }

  destroy(): void {
    this.transformer.destroy();
    for (const rect of this.rectByBBoxId.values()) rect.destroy();
    this.rectByBBoxId.clear();
    for (const label of this.labelByBBoxId.values()) label.destroy();
    this.labelByBBoxId.clear();
  }

  private _syncTransformer(): void {
    const id = this.ctx.collection.selectedId;
    const rect = id ? this.rectByBBoxId.get(id) : undefined;
    if (rect) {
      this.transformer.nodes([rect]);
      this.transformer.moveToTop();
    } else {
      this.transformer.nodes([]);
    }
    this.transformer.getLayer()?.batchDraw();
  }

  private _select(id: string | null): void {
    this.ctx.collection.select(id);
    this._syncTransformer();
  }

  private _commitRectGeometry(bboxId: string, rect: Konva.Rect): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    const bbox = this.ctx.collection.find(bboxId);
    if (!bbox) return;

    const coordsNorm = pixelToNormalized(rect.x(), rect.y(), rect.width(), rect.height(), frame);
    this.ctx.collection.setGeometry(bboxId, coordsNorm);

    if (bbox.persisted) {
      this.ctx.mutations.upsertUpdate({
        op: "update",
        resource: bboxPayloadBuilder.resource,
        id: bbox.id,
        body: bboxPayloadBuilder.buildUpdate(this.ctx.buildContext, bbox as LocalBBox),
        widgetId: this.ctx.widgetId,
        localAnnotationId: bbox.id,
      });
    } else {
      this.ctx.mutations.patchPendingCreate(bbox.id, bboxPayloadBuilder.resource, {
        coords: Array.from(coordsNorm),
      });
    }
  }

  private _positionLabel(label: Konva.Label, rect: Konva.Rect): void {
    const { x, y } = rect.position();
    label.position({ x, y: y - label.height() - 1 });
  }

  private _makeRect(bbox: LocalBBox, frame: PixelFrame | null): Konva.Rect | null {
    if (!frame) return null;
    const pixel = normalizedToPixel(bbox.geometry, frame);
    const stroke = bbox.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    const rect = new Konva.Rect({
      x: pixel.x,
      y: pixel.y,
      width: pixel.width,
      height: pixel.height,
      stroke,
      strokeWidth: 2,
      dash: bbox.persisted ? undefined : [6, 4],
      draggable: true,
      name: "bbox",
    });
    rect.setAttr("bboxId", bbox.id);
    rect.on("click tap", (e) => { e.cancelBubble = true; this._select(bbox.id); });
    rect.on("dragmove", () => {
      const lbl = this.labelByBBoxId.get(bbox.id);
      if (lbl) this._positionLabel(lbl, rect);
    });
    rect.on("dragend", () => {
      this._commitRectGeometry(bbox.id, rect);
      const lbl = this.labelByBBoxId.get(bbox.id);
      if (lbl) this._positionLabel(lbl, rect);
    });
    rect.on("transform", () => {
      const lbl = this.labelByBBoxId.get(bbox.id);
      if (lbl) this._positionLabel(lbl, rect);
    });
    rect.on("transformend", () => {
      const sx = rect.scaleX();
      const sy = rect.scaleY();
      rect.width(Math.max(1, rect.width() * sx));
      rect.height(Math.max(1, rect.height() * sy));
      rect.scaleX(1);
      rect.scaleY(1);
      this._commitRectGeometry(bbox.id, rect);
      const lbl = this.labelByBBoxId.get(bbox.id);
      if (lbl) this._positionLabel(lbl, rect);
    });
    return rect;
  }

  private _makeLabel(persisted: boolean, entity: Record<string, unknown> | undefined): Konva.Label | null {
    const text = pickEntityLabel(entity);
    if (!text) return null;
    const stroke = persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    const label = new Konva.Label({ listening: false });
    label.add(new Konva.Tag({ fill: stroke, cornerRadius: 3 }));
    label.add(new Konva.Text({ text, fontSize: 12, fontFamily: "system-ui, sans-serif", fill: "#0f172a", padding: 3 }));
    return label;
  }
}

export const bboxRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "bbox",
  create: (ctx: Scene2DContext) => new BBoxRenderer2D(ctx),
};
