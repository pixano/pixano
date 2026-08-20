/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { toPixelSubPaths } from "./multiPathGeometry.js";
import {
  MULTI_PATH_ID_ATTR,
  MULTI_PATH_NODE_NAME,
  MULTI_PATH_VERTEX_INDEX_ATTR,
  MULTI_PATH_VERTEX_NAME,
  type MultiPathGeometry,
} from "./multiPathTypes.js";
import type { LocalMultiPath } from "$lib/annotations/annotationCollection.svelte.js";
import { createFlatCoordsEditor2D } from "$lib/annotations/scene/flatCoordsEditor2D.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import { getPixelFrame, type PixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  drawVertexHitArea,
  SELECTED_OPACITY_BOOST,
  SELECTED_STROKE_SCALE,
  VERTEX_HIT_RADIUS,
} from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

const STROKE_WIDTH = 2;
const VERTEX_RADIUS = 3;
/** Closed rings get a wash of colour so the enclosed area reads as annotated. */
const POLYGON_FILL_OPACITY = 0.2;

/**
 * Displays the "multi_path" kind: one Konva line per sub-path, closed and
 * filled for polygons, open for polylines, plus a small handle on each vertex.
 * Read-only context, so it cannot write to the queue (D4) — drawing lives in
 * `drawMultiPathTool.ts`.
 *
 * Polygons are rendered `closed`, which makes Konva join the last point back to
 * the first. The backend stores rings *without* repeating the first point, so
 * letting Konva close the shape is what keeps the two representations aligned —
 * appending a duplicate point here would round-trip a longer ring on every save.
 */
class MultiPathRenderer2D implements AnnotationRenderer2D {
  readonly kind = "multi_path";

  private readonly groupById = new Map<string, Konva.Group>();

  constructor(private readonly ctx: Scene2DReadContext) {}

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const path of this.ctx.collection.byKind("multi_path")) {
      // Entity-driven visibility, as for every other kind.
      if (path.persisted && !this.ctx.isEntityVisible(path.entityId)) continue;
      if (!this._syncOne(path, frame)) continue;
      activeIds.add(path.id);
    }

    for (const [id, group] of this.groupById) {
      if (!activeIds.has(id)) {
        group.destroy();
        this.groupById.delete(id);
      }
    }

    this.ctx.annotationLayer.batchDraw();
  }

  /**
   * Rebuild one annotation's nodes. The sub-path count and their lengths are
   * both data, so the group is rebuilt rather than reconciled node by node —
   * a path is a handful of shapes.
   */
  private _syncOne(path: LocalMultiPath, frame: PixelFrame | null): boolean {
    if (!frame) return false;
    const subPaths = toPixelSubPaths(path.geometry, frame);
    if (subPaths.length === 0) return false;

    this.groupById.get(path.id)?.destroy();

    const color = path.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    const isClosed = path.geometry.isClosed;
    // Draggable as a whole, like a bbox: grabbing the shape moves it, and the
    // editor bakes the offset back into the coordinates on drag end.
    const group = new Konva.Group({ draggable: true });
    group.setAttr(MULTI_PATH_ID_ATTR, path.id);
    const isSelected = this.ctx.collection.selectedId === path.id;
    // Selection is display state, not a queue mutation, so it stays here.
    group.on("click tap", (e) => {
      e.cancelBubble = true;
      this.ctx.collection.select(path.id);
    });

    // Counts points across every sub-path, so ring 2's handles continue
    // where ring 1's stopped — the same order as the flat `coords` list.
    let pointIndex = 0;
    for (const points of subPaths) {
      group.add(
        new Konva.Line({
          points,
          stroke: color,
          // Selection has to be visible on the shape itself: unlike a bbox,
          // a path gets no transformer to announce it.
          strokeWidth: STROKE_WIDTH * (isSelected ? SELECTED_STROKE_SCALE : 1),
          closed: isClosed,
          fill: isClosed ? color : undefined,
          opacity: isClosed ? POLYGON_FILL_OPACITY + (isSelected ? SELECTED_OPACITY_BOOST : 0) : 1,
          name: MULTI_PATH_NODE_NAME,
          // With the handles hidden, an open polyline is a two-pixel thread —
          // this keeps the line itself grabbable without drawing it thicker.
          hitStrokeWidth: VERTEX_HIT_RADIUS,
        }),
      );

      // Handles are drawn only while the path is selected, the way a bbox shows
      // its transformer only then: a saved shape reads as a clean outline, and
      // the dots appear exactly when they can be dragged.
      if (!isSelected) {
        pointIndex += points.length / 2;
        continue;
      }

      for (let i = 0; i + 1 < points.length; i += 2) {
        const vertex = new Konva.Circle({
          x: points[i],
          y: points[i + 1],
          radius: VERTEX_RADIUS,
          fill: color,
          name: MULTI_PATH_VERTEX_NAME,
          draggable: true,
          // Grabbable well beyond the dot that is drawn — see VERTEX_HIT_RADIUS.
          hitFunc: drawVertexHitArea,
        });
        vertex.setAttr(MULTI_PATH_VERTEX_INDEX_ATTR, pointIndex);
        group.add(vertex);
        pointIndex += 1;
      }
    }

    this.ctx.annotationLayer.add(group);
    this.groupById.set(path.id, group);
    return true;
  }

  /**
   * No-op: a path is drawn inside this widget by its own tool, which owns its
   * live preview — there is no cross-widget gesture to mirror.
   */
  syncDraft(): void {}

  destroy(): void {
    for (const group of this.groupById.values()) group.destroy();
    this.groupById.clear();
  }
}

export const multiPathRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "multi_path",
  create: (ctx: Scene2DReadContext) => new MultiPathRenderer2D(ctx),
  createEditor: (ctx) =>
    createFlatCoordsEditor2D<MultiPathGeometry>(ctx, {
      kind: "multi_path",
      idAttr: MULTI_PATH_ID_ATTR,
      vertexName: MULTI_PATH_VERTEX_NAME,
      vertexIndexAttr: MULTI_PATH_VERTEX_INDEX_ATTR,
      readCoords: (geometry) => geometry.coords,
      // `numPoints` and `isClosed` survive an edit untouched: dragging moves
      // points, it never splits a ring or opens a closed one.
      withCoords: (geometry, coords) => ({ ...geometry, coords }),
    }),
};
