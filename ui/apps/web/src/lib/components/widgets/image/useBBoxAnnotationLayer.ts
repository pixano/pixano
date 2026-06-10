/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { buildBBoxUpdate } from "$lib/annotations/buildPayloads.js";
import type { ImageWidgetOptions, ImageWidgetStorage, LocalBBox } from "$lib/annotations/types.js";
import { pickEntityLabel } from "$lib/annotations/types.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  normalizedToPixel,
  type PixelFrame,
  pixelToNormalized,
} from "./imageWidgetGeometry.js";

export class BBoxAnnotationLayer {
  private readonly rectByBBoxId = new Map<string, Konva.Rect>();
  private readonly labelByBBoxId = new Map<string, Konva.Label>();
  readonly transformer: Konva.Transformer;

  constructor(
    private readonly layer: Konva.Layer,
    private readonly getKonvaImage: () => Konva.Image | null,
    private readonly storage: ImageWidgetStorage,
    private readonly manager: WorkspaceManager,
    private readonly widgetId: string,
    private readonly imgOptions: ImageWidgetOptions,
  ) {
    this.transformer = new Konva.Transformer({
      rotateEnabled: false,
      anchorStroke: BBOX_COLOR_PERSISTED,
      anchorFill: "#0f172a",
      borderStroke: BBOX_COLOR_PERSISTED,
      keepRatio: false,
      ignoreStroke: true,
    });
    layer.add(this.transformer);
  }

  redrawBoxes(): void {
    const frame = getPixelFrame(this.getKonvaImage());
    const activeIds = new Set<string>();

    for (const bbox of this.storage.bboxes) {
      activeIds.add(bbox.id);
      let rect = this.rectByBBoxId.get(bbox.id);
      if (!rect) {
        const newRect = this._makeRect(bbox, frame);
        if (!newRect) continue;
        this.layer.add(newRect);
        this.rectByBBoxId.set(bbox.id, newRect);
        rect = newRect;
      } else if (frame) {
        const pixel = normalizedToPixel(bbox.coordsNorm, frame);
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
          this.layer.add(label);
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

    this.syncTransformer();
    this.layer.batchDraw();
  }

  syncTransformer(): void {
    const id = this.storage.selectedId;
    if (!id) {
      this.transformer.nodes([]);
      this.transformer.getLayer()?.batchDraw();
      return;
    }
    const rect = this.rectByBBoxId.get(id);
    if (rect) {
      this.transformer.nodes([rect]);
      this.transformer.moveToTop();
    } else {
      this.transformer.nodes([]);
    }
    this.transformer.getLayer()?.batchDraw();
  }

  selectBBox(id: string | null): void {
    this.storage.selectedId = id;
    this.syncTransformer();
  }

  commitRectGeometry(bboxId: string, rect: Konva.Rect): void {
    const frame = getPixelFrame(this.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    const bbox = this.storage.bboxes.find((b) => b.id === bboxId);
    if (!bbox) return;

    const coordsNorm = pixelToNormalized(rect.x(), rect.y(), rect.width(), rect.height(), frame);
    bbox.coordsNorm = coordsNorm;

    if (bbox.persisted) {
      const ctx = {
        datasetId: this.imgOptions.datasetId,
        recordId: this.imgOptions.recordId,
        viewId: this.imgOptions.viewId,
      };
      const body = buildBBoxUpdate(ctx, bbox.id, bbox.entityId, coordsNorm);
      const existing = this.manager.pendingMutations.find(
        (m) => m.op === "update" && m.resource === "bboxes" && m.id === bbox.id,
      );
      if (existing && existing.op === "update") {
        existing.body = body;
      } else {
        this.manager.queueMutation({
          op: "update",
          resource: "bboxes",
          id: bbox.id,
          body,
          widgetId: this.widgetId,
          localBBoxId: bbox.id,
        });
      }
    } else {
      const pending = this.manager.pendingMutations.find(
        (m) =>
          m.op === "create" &&
          m.resource === "bboxes" &&
          m.widgetId === this.widgetId &&
          m.localBBoxId === bbox.id,
      );
      if (pending && pending.op === "create") {
        (pending.body as Record<string, unknown>).coords = Array.from(coordsNorm);
      }
    }
  }

  deleteSelected(): void {
    const id = this.storage.selectedId;
    if (!id) return;
    const bbox = this.storage.bboxes.find((b) => b.id === id);
    if (!bbox) return;

    if (bbox.persisted) {
      this.manager.queueMutation({
        op: "delete",
        resource: "bboxes",
        id: bbox.id,
        widgetId: this.widgetId,
        localBBoxId: bbox.id,
      });
      this.manager.queueMutation({
        op: "delete",
        resource: "entities",
        id: bbox.entityId,
        widgetId: this.widgetId,
        localBBoxId: bbox.id,
      });
    } else {
      this.manager.dropMutationsForLocalBBox(bbox.id);
    }

    this.storage.bboxes = this.storage.bboxes.filter((b) => b.id !== bbox.id);
    this.storage.selectedId = null;
    this.redrawBoxes();
  }

  destroy(): void {
    this.transformer.destroy();
    for (const rect of this.rectByBBoxId.values()) rect.destroy();
    this.rectByBBoxId.clear();
    for (const label of this.labelByBBoxId.values()) label.destroy();
    this.labelByBBoxId.clear();
  }

  private _positionLabel(label: Konva.Label, rect: Konva.Rect): void {
    const { x, y } = rect.position();
    label.position({ x, y: y - label.height() - 1 });
  }

  private _makeRect(bbox: LocalBBox, frame: PixelFrame | null): Konva.Rect | null {
    if (!frame) return null;
    const pixel = normalizedToPixel(bbox.coordsNorm, frame);
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
    rect.on("click tap", (e) => { e.cancelBubble = true; this.selectBBox(bbox.id); });
    rect.on("dragmove", () => {
      const lbl = this.labelByBBoxId.get(bbox.id);
      if (lbl) this._positionLabel(lbl, rect);
    });
    rect.on("dragend", () => {
      this.commitRectGeometry(bbox.id, rect);
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
      this.commitRectGeometry(bbox.id, rect);
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
