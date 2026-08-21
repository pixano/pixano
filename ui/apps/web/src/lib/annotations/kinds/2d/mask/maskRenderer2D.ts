/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { createMaskEditor2D } from "./maskEditor2D.js";
import { decodeMask, maskBounds, tintMask, type MaskCanvas } from "./maskRaster.js";
import { MASK_ID_ATTR, MASK_NODE_NAME } from "./maskTypes.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import { EntityLabels2D, type EntityLabelEntry } from "$lib/annotations/scene/entityLabels2D.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import { getPixelFrame, type PixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  SELECTED_OPACITY_BOOST,
} from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";
import { rleFrString } from "$lib/utils/maskUtils.js";

/** Masks are filled areas, so they are drawn translucent to keep the image readable. */
const MASK_OPACITY = 0.45;

/**
 * Alpha above which a pixel counts as part of the mask for hit-testing. The
 * raster is drawn at `MASK_OPACITY`, so the threshold sits below that: high
 * enough to exclude the fully transparent background, low enough to keep the
 * whole painted region clickable.
 */
const HIT_ALPHA_THRESHOLD = 0.1;

/**
 * What a cached node was built from. Decoding an RLE is the expensive part of a
 * sync, and `sync()` runs on every collection change — so a mask is only
 * re-rasterised when its encoding or its colour actually changed, not when a
 * neighbouring annotation moved.
 */
interface CachedMask {
  node: Konva.Image;
  counts: string;
  color: string;
  /** Part of the key: the tint bakes opacity in, so selection re-rasterises. */
  opacity: number;
  /** Where the paint sits in the grid; recomputed with the raster. */
  bounds: ReturnType<typeof maskBounds>;
}

/**
 * Displays the "mask" kind: one raster image per annotation, scaled onto the
 * frame the image currently occupies, click-to-select. Read-only context, so it
 * cannot write to the queue (D4) — painting lives in `drawMaskTool.ts`.
 */
class MaskRenderer2D implements AnnotationRenderer2D {
  readonly kind = "mask";

  private readonly cacheByMaskId = new Map<string, CachedMask>();
  private readonly labels: EntityLabels2D;

  constructor(private readonly ctx: Scene2DReadContext) {
    this.labels = new EntityLabels2D(ctx.annotationLayer);
  }

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const mask of this.ctx.collection.byKind("mask")) {
      // Entity-driven visibility, as for boxes: a persisted mask whose entity is
      // hidden gets no node, so it is invisible AND non-clickable. Drafts are
      // always shown.
      if (mask.persisted && !this.ctx.isEntityVisible(mask.entityId)) continue;
      if (!this._syncOne(mask, frame)) continue;
      activeIds.add(mask.id);
    }

    for (const [id, cached] of this.cacheByMaskId) {
      if (!activeIds.has(id)) {
        cached.node.destroy();
        this.cacheByMaskId.delete(id);
      }
    }

    this.labels.sync(this._labelEntries(activeIds, frame));
    this.ctx.annotationLayer.batchDraw();
  }

  /** Create or update one mask's node. Returns false when it can't be drawn. */
  private _syncOne(mask: LocalMask, frame: PixelFrame | null): boolean {
    if (!frame) return false;
    const color = mask.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    // A selected mask reads as more solid. It has to go through the tint —
    // the raster's alpha is baked in, and Konva's node opacity can only scale
    // that down — which is why selection belongs in the cache key.
    const opacity =
      this.ctx.collection.selectedId === mask.id
        ? MASK_OPACITY + SELECTED_OPACITY_BOOST
        : MASK_OPACITY;
    const cached = this.cacheByMaskId.get(mask.id);

    if (cached) {
      // Only the geometry, the colour and the selected state justify
      // re-rasterising; a frame change is absorbed by repositioning the node.
      if (
        cached.counts !== mask.geometry.counts ||
        cached.color !== color ||
        cached.opacity !== opacity
      ) {
        const raster = this._rasterise(mask, color, opacity);
        if (!raster) return false;
        cached.node.image(raster as unknown as CanvasImageSource);
        cached.counts = mask.geometry.counts;
        cached.color = color;
        cached.opacity = opacity;
        cached.bounds = maskBounds(rleFrString(mask.geometry.counts), mask.geometry.size);
        this._restrictHitAreaToPaintedPixels(cached.node);
      }
      this._placeNode(cached.node, frame);
      return true;
    }

    const raster = this._rasterise(mask, color, opacity);
    if (!raster) return false;
    const node = new Konva.Image({
      image: raster as unknown as CanvasImageSource,
      name: MASK_NODE_NAME,
      listening: true,
      // Draggable like a bbox: moving the painted region is the one edit a
      // raster supports, and `maskEditor2D` turns the drop into a new RLE.
      draggable: true,
    });
    node.setAttr(MASK_ID_ATTR, mask.id);
    // Selection is display state, not a queue mutation, so it stays here.
    node.on("click tap", (e) => {
      e.cancelBubble = true;
      this.ctx.collection.select(mask.id);
    });
    // Keep the label glued to the paint while the raster is dragged.
    node.on("dragmove", () => this._followLabel(mask.id));
    this._restrictHitAreaToPaintedPixels(node);
    this._placeNode(node, frame);
    this.ctx.annotationLayer.add(node);
    this.cacheByMaskId.set(mask.id, {
      node,
      counts: mask.geometry.counts,
      color,
      opacity,
      bounds: maskBounds(rleFrString(mask.geometry.counts), mask.geometry.size),
    });
    return true;
  }

  private _followLabel(id: string): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const [entry] = this._labelEntries(new Set([id]), frame);
    if (entry) this.labels.moveTo(id, entry.anchor);
  }

  /**
   * Hang each mask's label off the top-left of the paint, not of the raster.
   * A mask's grid is the whole media, so anchoring on the node would park every
   * label in the image's corner, far from the region it names.
   */
  private _labelEntries(
    activeIds: ReadonlySet<string>,
    frame: PixelFrame | null,
  ): EntityLabelEntry[] {
    if (!frame) return [];
    const entries: EntityLabelEntry[] = [];
    for (const mask of this.ctx.collection.byKind("mask")) {
      if (!activeIds.has(mask.id)) continue;
      const cached = this.cacheByMaskId.get(mask.id);
      const bounds = cached?.bounds;
      if (!bounds) continue;
      const [gridHeight, gridWidth] = mask.geometry.size;
      if (!gridWidth || !gridHeight) continue;
      entries.push({
        id: mask.id,
        annotation: mask,
        anchor: {
          // The node carries the drag offset until the next resync bakes it in.
          x: cached.node.x() + (bounds.x * frame.w) / gridWidth,
          y: cached.node.y() + (bounds.y * frame.h) / gridHeight,
        },
      });
    }
    return entries;
  }

  /**
   * Make only the painted pixels clickable.
   *
   * A mask's raster spans the whole image grid and is transparent outside the
   * painted region, but `Konva.Image` hit-tests its **bounding rectangle**. Left
   * alone, one saved mask therefore swallows every click on the image and no
   * other annotation can be selected again — which is exactly what happened
   * before this call existed. `drawHitFromCache` rebuilds the hit graph from the
   * cached pixels instead, so transparent areas fall through to whatever is
   * underneath.
   *
   * Caching is what makes that possible, and it is cheap here: it happens once
   * per rasterisation, on the same schedule as the decode it follows.
   */
  private _restrictHitAreaToPaintedPixels(node: Konva.Image): void {
    try {
      node.cache();
      node.drawHitFromCache(HIT_ALPHA_THRESHOLD);
    } catch {
      // A zero-sized or unsupported canvas leaves the node with its default
      // rectangular hit area — worse for picking, but still drawn correctly.
    }
  }

  private _rasterise(mask: LocalMask, color: string, opacity: number): MaskCanvas | null {
    const decoded = decodeMask(mask.geometry);
    if (!decoded) return null;
    return tintMask(decoded, color, opacity);
  }

  /**
   * The raster is in the mask's own pixel grid; the image on screen may be any
   * size. Scaling the node maps one onto the other, so a window resize needs no
   * re-decode.
   */
  private _placeNode(node: Konva.Image, frame: PixelFrame): void {
    const raster = node.image();
    const sourceWidth = (raster as OffscreenCanvas | undefined)?.width ?? 0;
    const sourceHeight = (raster as OffscreenCanvas | undefined)?.height ?? 0;
    node.position({ x: frame.x, y: frame.y });
    node.scale({
      x: sourceWidth > 0 ? frame.w / sourceWidth : 1,
      y: sourceHeight > 0 ? frame.h / sourceHeight : 1,
    });
  }

  /**
   * No-op: a mask is painted inside this widget by its own brush, which owns
   * its live preview — there is no cross-widget gesture to mirror.
   */
  syncDraft(): void {}

  destroy(): void {
    this.labels.destroy();
    for (const cached of this.cacheByMaskId.values()) cached.node.destroy();
    this.cacheByMaskId.clear();
  }
}

export const maskRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "mask",
  create: (ctx: Scene2DReadContext) => new MaskRenderer2D(ctx),
  // Moving only: a painted region has no transform handles that map back to a
  // sensible RLE, so reshaping stays in the brush tool.
  createEditor: createMaskEditor2D,
};
