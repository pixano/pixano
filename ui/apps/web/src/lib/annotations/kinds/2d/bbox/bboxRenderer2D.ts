/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { BBOX_ID_ATTR, BBOX_NODE_NAME } from "./bbox2dNodes.js";
import { createBBoxEditor2D } from "./bboxEditor2D.js";
import type { LocalBBox } from "$lib/annotations/annotationCollection.svelte.js";
import { EntityLabels2D, type EntityLabelEntry } from "$lib/annotations/scene/entityLabels2D.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import {
  getPixelFrame,
  normalizedToPixel,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  DRAFT_DASH,
} from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

/**
 * Displays the "bbox" kind on the Konva scene: one rect (+ optional entity
 * label) per annotation, click-to-select, and label-follow while a node is
 * dragged or transformed. It receives a read-only context and so cannot write
 * to the queue — the drag/transform → commit path lives in `bboxEditor2D.ts` (D4).
 */
class BBoxRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox";

  private readonly rectByBBoxId = new Map<string, Konva.Rect>();
  private readonly labels: EntityLabels2D;

  constructor(private readonly ctx: Scene2DReadContext) {
    this.labels = new EntityLabels2D(ctx.annotationLayer);
  }

  sync(): void {
    const labelEntries: EntityLabelEntry[] = [];
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
        rect.dash(bbox.persisted ? [] : [...DRAFT_DASH]);
      }

      labelEntries.push({ id: bbox.id, annotation: bbox, anchor: rect.position() });
    }

    for (const [id, rect] of this.rectByBBoxId) {
      if (!activeIds.has(id)) {
        rect.destroy();
        this.rectByBBoxId.delete(id);
      }
    }
    this.labels.sync(labelEntries);

    this.ctx.annotationLayer.batchDraw();
  }

  /**
   * No-op: a 2D box is drawn inside this widget by its own draw tool, which
   * owns its rubber-band preview — there is no cross-widget gesture to mirror.
   * The draft an image widget could receive here is always another medium's.
   */
  syncDraft(): void {}

  destroy(): void {
    for (const rect of this.rectByBBoxId.values()) rect.destroy();
    this.rectByBBoxId.clear();
    this.labels.destroy();
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
      dash: bbox.persisted ? undefined : [...DRAFT_DASH],
      draggable: true,
      name: BBOX_NODE_NAME,
    });
    rect.setAttr(BBOX_ID_ATTR, bbox.id);
    // Selection is display state, not a queue mutation, so it stays in the renderer.
    rect.on("click tap", (e) => {
      e.cancelBubble = true;
      this.ctx.collection.select(bbox.id);
    });
    // Keep the label glued to the box while the editor drags/transforms it.
    rect.on("dragmove transform", () => this.labels.moveTo(bbox.id, rect.position()));
    return rect;
  }
}

export const bboxRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "bbox",
  create: (ctx: Scene2DReadContext) => new BBoxRenderer2D(ctx),
  createEditor: createBBoxEditor2D,
};
