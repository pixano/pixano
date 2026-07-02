/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import type { AnnotationEditor2D } from "$lib/annotations/scene/renderer.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import {
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  pixelToNormalized,
} from "$lib/annotations/scene/scene2dGeometry.js";

import { BBOX_ID_ATTR, BBOX_NODE_NAME } from "./bbox2dNodes.js";

const MIN_BBOX_PIXELS = 1;

/**
 * Editing input for the "bbox" kind: owns the `Konva.Transformer` and commits
 * drag/transform results back through `commitGeometryEdit`. It never creates the
 * box nodes (that is the renderer's job) — it finds them by their stamped id and
 * listens at the **layer** level, so display and input stay decoupled (D4).
 */
class BBoxEditor2D implements AnnotationEditor2D {
  readonly kind = "bbox" as const;

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

    // Layer-delegated: catches drag/transform of any bbox node without the editor
    // owning node creation. Namespaced so `destroy()` removes exactly these.
    ctx.annotationLayer.on("dragend.bbox-edit", (e) => this._commitNode(e.target));
    ctx.annotationLayer.on("transformend.bbox-edit", (e) => this._onTransformEnd(e.target));
  }

  /** Attach the transformer to the selected bbox node (or detach if none). */
  syncSelection(): void {
    const id = this.ctx.collection.selectedId;
    const node = id ? this._findNode(id) : null;
    if (node) {
      this.transformer.nodes([node]);
      this.transformer.moveToTop();
    } else {
      this.transformer.nodes([]);
    }
    this.transformer.getLayer()?.batchDraw();
  }

  destroy(): void {
    this.ctx.annotationLayer.off("dragend.bbox-edit");
    this.ctx.annotationLayer.off("transformend.bbox-edit");
    this.transformer.destroy();
  }

  private _findNode(id: string): Konva.Node | null {
    const nodes = this.ctx.annotationLayer.find(`.${BBOX_NODE_NAME}`);
    return nodes.find((n) => n.getAttr(BBOX_ID_ATTR) === id) ?? null;
  }

  private _bboxId(node: Konva.Node): string | null {
    if (node.name() !== BBOX_NODE_NAME) return null;
    return (node.getAttr(BBOX_ID_ATTR) as string | undefined) ?? null;
  }

  /** A transform ends as a scale on the node; bake it into width/height first. */
  private _onTransformEnd(node: Konva.Node): void {
    if (this._bboxId(node) === null) return;
    const rect = node as Konva.Rect;
    rect.width(Math.max(MIN_BBOX_PIXELS, rect.width() * rect.scaleX()));
    rect.height(Math.max(MIN_BBOX_PIXELS, rect.height() * rect.scaleY()));
    rect.scaleX(1);
    rect.scaleY(1);
    this._commitNode(rect);
  }

  private _commitNode(node: Konva.Node): void {
    const id = this._bboxId(node);
    if (id === null) return;
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;
    const rect = node as Konva.Rect;
    const coordsNorm = pixelToNormalized(rect.x(), rect.y(), rect.width(), rect.height(), frame);
    commitGeometryEdit(this.ctx, id, coordsNorm);
  }
}

export function createBBoxEditor2D(ctx: Scene2DContext): AnnotationEditor2D {
  return new BBoxEditor2D(ctx);
}
