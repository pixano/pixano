/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import type { LocalBBox } from "$lib/annotations/annotationCollection.svelte.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  normalizedToPixel,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import { pickEntityLabel } from "$lib/annotations/types.js";

import { BBOX_ID_ATTR, BBOX_NODE_NAME } from "./bbox2dNodes.js";
import { createBBoxEditor2D } from "./bboxEditor2D.js";

/**
 * Displays the "bbox" kind on the Konva scene: one rect (+ optional entity
 * label) per annotation, click-to-select, and label-follow while a node is
 * dragged or transformed. It receives a read-only context and so cannot write
 * to the queue — the drag/transform → commit path lives in `bboxEditor2D.ts` (D4).
 */
class BBoxRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox" as const;

  private readonly rectByBBoxId = new Map<string, Konva.Rect>();
  private readonly labelByBBoxId = new Map<string, Konva.Label>();

  constructor(private readonly ctx: Scene2DReadContext) {}

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const bbox of this.ctx.collection.byKind("bbox")) {
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

    this.ctx.annotationLayer.batchDraw();
  }

  destroy(): void {
    for (const rect of this.rectByBBoxId.values()) rect.destroy();
    this.rectByBBoxId.clear();
    for (const label of this.labelByBBoxId.values()) label.destroy();
    this.labelByBBoxId.clear();
  }

  private _positionLabel(label: Konva.Label, rect: Konva.Rect): void {
    const { x, y } = rect.position();
    label.position({ x, y: y - label.height() - 1 });
  }

  private _followLabel(bboxId: string, rect: Konva.Rect): void {
    const lbl = this.labelByBBoxId.get(bboxId);
    if (lbl) this._positionLabel(lbl, rect);
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
      name: BBOX_NODE_NAME,
    });
    rect.setAttr(BBOX_ID_ATTR, bbox.id);
    // Selection is display state, not a queue mutation, so it stays in the renderer.
    rect.on("click tap", (e) => { e.cancelBubble = true; this.ctx.collection.select(bbox.id); });
    // Keep the label glued to the box while the editor drags/transforms it.
    rect.on("dragmove transform", () => this._followLabel(bbox.id, rect));
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
  create: (ctx: Scene2DReadContext) => new BBoxRenderer2D(ctx),
  createEditor: createBBoxEditor2D,
};
