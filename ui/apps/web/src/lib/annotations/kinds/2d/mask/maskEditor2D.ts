/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import { translateMask } from "./maskRaster.js";
import {
  MASK_DRAGGING_ATTR,
  MASK_ID_ATTR,
  MASK_NODE_NAME,
  type MaskGeometry,
} from "./maskTypes.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import type { AnnotationEditor2D } from "$lib/annotations/scene/renderer.js";
import { getPixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext, StagedWorkFlag } from "$lib/annotations/scene/sceneContext.js";

/**
 * Editing input for the "mask" kind: dragging a painted region moves it.
 *
 * This is the only edit gesture a raster supports. There are no transform
 * handles, because a mask has no corners that map back onto an RLE — resizing
 * one would mean resampling the stamp, which invents pixels the annotator never
 * painted. Reshaping stays where it belongs, in the brush.
 *
 * A drag is work of its own until it ends: the new place sits on the node, not
 * in the collection. So the editor raises its staged-work flag while one runs —
 * the record counts it as one unsaved item, and Discard or a delete pressed
 * mid-drag drops it — and stamps the node (`MASK_DRAGGING_ATTR`) so that the
 * renderer's sync leaves it alone. The drag commits onto the mask's row, by its
 * id, when it ends.
 *
 * Like the other editors it never creates nodes (the renderer owns those, D4)
 * and listens at the **layer**, namespaced so `destroy()` removes exactly its
 * own handlers.
 */
class MaskEditor2D implements AnnotationEditor2D {
  readonly kind = "mask";

  /** Raised while a drag runs. */
  private readonly staged: StagedWorkFlag | undefined;
  /** The masks being dragged, each from its dragstart to its dragend. */
  private readonly dragging = new Set<Konva.Node>();

  constructor(private readonly ctx: Scene2DContext) {
    this.staged = ctx.claimStagedWork?.(() => this._abandonDrags());
    // A drag's start and end bubble up from the node, so the layer hears them
    // for every mask node without the editor owning node creation.
    ctx.annotationLayer.on("dragstart.mask-edit", (e) => this._startDrag(e.target));
    ctx.annotationLayer.on("dragend.mask-edit", (e) => this._endDrag(e.target));
  }

  /** No transformer to attach — the draggable raster is its own handle. */
  syncSelection(): void {}

  destroy(): void {
    this.ctx.annotationLayer.off("dragstart.mask-edit dragend.mask-edit");
    // A drag cut short with the editor can no longer be confirmed.
    this._releaseDragging();
    this.staged?.set(false);
  }

  private _maskId(node: Konva.Node): string | null {
    if (node.name() !== MASK_NODE_NAME) return null;
    return (node.getAttr(MASK_ID_ATTR) as string | undefined) ?? null;
  }

  /** A drag of a mask begins: hold the mask, and the flag, until the drag ends. */
  private _startDrag(node: Konva.Node): void {
    if (this._maskId(node) === null) return;
    this.dragging.add(node);
    node.setAttr(MASK_DRAGGING_ATTR, true);
    this._updateStaged();
  }

  /** A drag ends: commit the mask where it was let go. */
  private _endDrag(node: Konva.Node): void {
    // A drag Discard dropped ends here too, as Konva stops it: nothing to commit.
    if (!this.dragging.delete(node)) return;
    // Let go first: the commit redraws, and the renderer must then place the
    // node back on the image, the move baked into the new mask.
    node.setAttr(MASK_DRAGGING_ATTR, false);
    this._commitDrag(node);
    this._updateStaged();
  }

  /**
   * Discard: the running drags are dropped. Ended here, they commit nothing,
   * and their masks are drawn again as the collection holds them.
   */
  private _abandonDrags(): void {
    const abandoned = this._releaseDragging();
    this._updateStaged();
    // Konva ends each as a release would, which reaches `_endDrag` with no mask held.
    for (const node of abandoned) if (node.isDragging()) node.stopDrag();
    if (abandoned.length > 0) this.ctx.requestRedraw();
  }

  /**
   * Raise the flag while a drag runs, lower it once none does. Called as a
   * drag starts and ends, never as the pointer moves.
   */
  private _updateStaged(): void {
    this.staged?.set(this.dragging.size > 0);
  }

  /** Let go of the masks being dragged, and return them. */
  private _releaseDragging(): Konva.Node[] {
    const released = [...this.dragging];
    this.dragging.clear();
    for (const node of released) node.setAttr(MASK_DRAGGING_ATTR, false);
    return released;
  }

  private _commitDrag(node: Konva.Node): void {
    const id = this._maskId(node);
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

    // A drag too small to reach a whole grid pixel is not an edit: without
    // this the record would go dirty and a no-op PUT would be sent for a stray
    // one-pixel nudge. `flatCoordsEditor2D` guards the same way.
    if (Math.round(dx) === 0 && Math.round(dy) === 0) {
      this.ctx.requestRedraw();
      return;
    }

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
