/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { BBOX_ID_ATTR, BBOX_NODE_NAME } from "./bbox2dNodes.js";
import { cutAtImageEdges, movedInsideImage } from "./bboxImageBounds.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import type { AnnotationEditor2D } from "$lib/annotations/scene/renderer.js";
import {
  getPixelFrame,
  pixelToNormalized,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import { BBOX_COLOR_PERSISTED } from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import type { CoordsNorm } from "$lib/annotations/types.js";

/** The least width and height, in image pixels, a resize leaves a box with. */
const MIN_BBOX_PIXELS = 1;

/**
 * Editing input for the "bbox" kind: owns the `Konva.Transformer` and commits
 * drag/transform results back through `commitGeometryEdit`. It never creates the
 * box nodes (that is the renderer's job) — it finds them by their stamped id and
 * listens where Konva reports the gestures, so display and input stay decoupled (D4).
 *
 * A box is committed inside the image, which the server requires: dragged past
 * an edge, it stops against it, whole; resized past one, it is cut at it
 * (`bboxImageBounds`), never smaller than a resize leaves a box.
 */
class BBoxEditor2D implements AnnotationEditor2D {
  readonly kind = "bbox";

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

    // A drag's end bubbles up from the node, so the layer hears it for any bbox
    // node without the editor owning node creation. A resize's end does not
    // bubble: Konva fires it on the transformer and on each node it holds, never
    // on their layer — listened for on the layer, a resize was never saved. The
    // transformer is the editor's own, so it is heard there. Namespaced so
    // `destroy()` removes exactly these.
    ctx.annotationLayer.on("dragend.bbox-edit", (e) => this._endDrag(e.target));
    this.transformer.on("transformend.bbox-edit", () => this._endResize());
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
    this.transformer.off("transformend.bbox-edit");
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

  /** A resize ends: commit the boxes it acted on. */
  private _endResize(): void {
    const resized = this.transformer.nodes();
    for (const node of resized) this._onTransformEnd(node);
    // A box resized past the image's edge is saved cut at it: draw it so.
    if (resized.length > 0) this.ctx.requestRedraw();
  }

  /** A drag ends: commit the box where it was let go, inside the image. */
  private _endDrag(node: Konva.Node): void {
    if (this._bboxId(node) === null) return;
    this._commitNode(node, movedInsideImage);
    // A box dropped past the image's edge is saved against it: draw it so.
    this.ctx.requestRedraw();
  }

  /** A transform ends as a scale on the node; bake it into width/height first. */
  private _onTransformEnd(node: Konva.Node): void {
    if (this._bboxId(node) === null) return;
    const rect = node as Konva.Rect;
    rect.width(Math.max(MIN_BBOX_PIXELS, rect.width() * rect.scaleX()));
    rect.height(Math.max(MIN_BBOX_PIXELS, rect.height() * rect.scaleY()));
    rect.scaleX(1);
    rect.scaleY(1);
    // The cut keeps the least size the lines above give the box: resized
    // wholly beyond an edge, it would otherwise be saved with no width or height.
    this._commitNode(rect, (coords, frame) =>
      cutAtImageEdges(coords, {
        width: MIN_BBOX_PIXELS / frame.w,
        height: MIN_BBOX_PIXELS / frame.h,
      }),
    );
  }

  /**
   * Commit the box a node holds, bounded to the image first: the server
   * refuses a box reaching past it, and a save stuck on that refusal fails
   * until the box is moved back.
   *
   * A box stored with no width or height cannot be resized: Konva scales it by
   * dividing by that size, and leaves its node with no number for a place or a
   * size. Nothing is committed then — bounded to the image, those would make a
   * box out of nothing — and the box is drawn again as stored.
   *
   * @param node The box's node, let go of.
   * @param keepInImage How the gesture's box is brought inside the image the
   *   frame shows — normalized coordinates, and the frame they are a share of.
   */
  private _commitNode(
    node: Konva.Node,
    keepInImage: (coords: CoordsNorm, frame: PixelFrame) => CoordsNorm,
  ): void {
    const id = this._bboxId(node);
    if (id === null) return;
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;
    const rect = node as Konva.Rect;
    const coordsNorm = pixelToNormalized(rect.x(), rect.y(), rect.width(), rect.height(), frame);
    if (!coordsNorm.every(Number.isFinite)) return;
    commitGeometryEdit(this.ctx, id, keepInImage(coordsNorm, frame));
  }
}

export function createBBoxEditor2D(ctx: Scene2DContext): AnnotationEditor2D {
  return new BBoxEditor2D(ctx);
}
