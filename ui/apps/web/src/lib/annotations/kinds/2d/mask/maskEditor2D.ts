/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import { translateMask } from "./maskRaster.js";
import { MASK_ID_ATTR, MASK_NODE_NAME, type MaskGeometry } from "./maskTypes.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import type { AnnotationEditor2D } from "$lib/annotations/scene/renderer.js";
import { getPixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";

/**
 * Editing input for the "mask" kind: dragging a painted region moves it.
 *
 * This is the only edit gesture a raster supports. There are no transform
 * handles, because a mask has no corners that map back onto an RLE — resizing
 * one would mean resampling the stamp, which invents pixels the annotator never
 * painted. Reshaping stays where it belongs, in the brush.
 *
 * Like the other editors it never creates nodes (the renderer owns those, D4)
 * and listens at the **layer**, namespaced so `destroy()` removes exactly its
 * own handler.
 */
class MaskEditor2D implements AnnotationEditor2D {
  readonly kind = "mask";

  constructor(private readonly ctx: Scene2DContext) {
    ctx.annotationLayer.on("dragend.mask-edit", (e) => this._onDragEnd(e.target));
  }

  /** No transformer to attach — the draggable raster is its own handle. */
  syncSelection(): void {}

  destroy(): void {
    this.ctx.annotationLayer.off("dragend.mask-edit");
  }

  private _onDragEnd(node: Konva.Node): void {
    if (node.name() !== MASK_NODE_NAME) return;
    const id = node.getAttr(MASK_ID_ATTR) as string | undefined;
    if (!id) return;

    const annotation = this.ctx.collection.find(id);
    if (!annotation) return;
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    // The renderer parks the raster on the image's frame and scales it to fit,
    // so how far the node strayed from that origin *is* the drag — expressed in
    // stage pixels, which the mask's own grid does not share.
    const geometry = annotation.geometry as MaskGeometry;
    const [gridHeight, gridWidth] = geometry.size;
    if (!gridWidth || !gridHeight) return;
    const dx = ((node.x() - frame.x) * gridWidth) / frame.w;
    const dy = ((node.y() - frame.y) * gridHeight) / frame.h;

    const moved = translateMask(geometry, dx, dy);
    // A failed re-encode (no OffscreenCanvas, or the mask dragged entirely off
    // the media) must not commit an empty mask; the resync snaps the node back.
    if (!moved) {
      this.ctx.requestRedraw();
      return;
    }

    commitGeometryEdit(this.ctx, id, moved);
    this.ctx.requestRedraw();
  }
}

export function createMaskEditor2D(ctx: Scene2DContext): AnnotationEditor2D {
  return new MaskEditor2D(ctx);
}
