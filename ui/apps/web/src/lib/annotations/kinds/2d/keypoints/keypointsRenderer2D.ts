/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { keypointTemplateFor } from "./keypointsTemplates.js";
import {
  KEYPOINTS_EDGE_NAME,
  KEYPOINTS_ID_ATTR,
  KEYPOINTS_VERTEX_INDEX_ATTR,
  KEYPOINTS_VERTEX_NAME,
  type KeypointsGeometry,
} from "./keypointsTypes.js";
import type { LocalKeypoints } from "$lib/annotations/annotationCollection.svelte.js";
import { EntityLabels2D, type EntityLabelEntry } from "$lib/annotations/scene/entityLabels2D.js";
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
  SELECTED_STROKE_SCALE,
  VERTEX_HIT_RADIUS,
} from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

const VERTEX_RADIUS = 4;
const VERTEX_STROKE_WIDTH = 2;
const EDGE_STROKE_WIDTH = 2;
/** An "invisible" point is annotated but occluded: shown hollow, not filled. */
const INVISIBLE_FILL = "transparent";

/** One skeleton's nodes, kept together so a resync can move them in place. */
interface SkeletonNodes {
  group: Konva.Group;
  vertices: Konva.Circle[];
  edges: Konva.Line[];
}

/**
 * Displays the "keypoints" kind: the template's bones as lines, each annotated
 * point as a circle, click-to-select on the whole skeleton. Read-only context,
 * so it cannot write to the queue (D4) — placing points lives in
 * `drawKeypointsTool.ts`.
 *
 * A point whose state is "hidden" is not drawn at all, and neither is any bone
 * touching it: "hidden" means the annotator asserted the point is absent, so
 * drawing a bone into empty space would invent a limb that was never annotated.
 */
class KeypointsRenderer2D implements AnnotationRenderer2D {
  readonly kind = "keypoints";

  private readonly nodesById = new Map<string, SkeletonNodes>();
  private readonly labels: EntityLabels2D;

  constructor(private readonly ctx: Scene2DReadContext) {
    this.labels = new EntityLabels2D(ctx.annotationLayer);
  }

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const skeleton of this.ctx.collection.byKind("keypoints")) {
      // Entity-driven visibility, as for every other kind.
      if (skeleton.persisted && !this.ctx.isEntityVisible(skeleton.entityId)) continue;
      if (!this._syncOne(skeleton, frame)) continue;
      activeIds.add(skeleton.id);
    }

    for (const [id, nodes] of this.nodesById) {
      if (!activeIds.has(id)) {
        nodes.group.destroy();
        this.nodesById.delete(id);
      }
    }

    this.labels.sync(this._labelEntries(activeIds));
    this.ctx.annotationLayer.batchDraw();
  }

  /**
   * Rebuild one skeleton's nodes. A skeleton's node *count* depends on its
   * template and its per-point states, both of which can change between syncs,
   * so the group is rebuilt rather than reconciled node by node — a skeleton is
   * a handful of shapes, unlike a mask raster where re-decoding is the cost.
   */
  private _syncOne(skeleton: LocalKeypoints, frame: PixelFrame | null): boolean {
    if (!frame) return false;
    const points = this._toPixels(skeleton.geometry, frame);
    if (points.length === 0) return false;

    this.nodesById.get(skeleton.id)?.group.destroy();

    const color = skeleton.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    // Draggable as a whole, like a bbox: grabbing the skeleton moves every
    // point at once, and the editor bakes the offset back in on drag end.
    const group = new Konva.Group({ draggable: true });
    group.setAttr(KEYPOINTS_ID_ATTR, skeleton.id);
    const isSelected = this.ctx.collection.selectedId === skeleton.id;
    // Selection is display state, not a queue mutation, so it stays here.
    group.on("click tap", (e) => {
      e.cancelBubble = true;
      this.ctx.collection.select(skeleton.id);
    });
    // Keep the label glued to the skeleton while it is dragged.
    group.on("dragmove", () => this._followLabel(skeleton.id));

    const template = keypointTemplateFor(skeleton.geometry.templateId);
    const states = skeleton.geometry.states;
    const edges: Konva.Line[] = [];
    for (const [from, to] of template?.edges ?? []) {
      // Guard the indices: an edge is template data, the point count is row
      // data, and an import can leave the two disagreeing.
      if (from >= points.length || to >= points.length) continue;
      if (states[from] === "hidden" || states[to] === "hidden") continue;
      const line = new Konva.Line({
        points: [points[from].x, points[from].y, points[to].x, points[to].y],
        stroke: color,
        // The bones carry the selected look: they are the only part of a
        // skeleton big enough to read at a glance, and nothing else announces
        // selection for this kind.
        strokeWidth: EDGE_STROKE_WIDTH * (isSelected ? SELECTED_STROKE_SCALE : 1),
        // The bones must be grabbable, not inert. They are the only part of a
        // skeleton that is not a vertex, so with them deaf the group could only
        // be caught through a handle — and once selected a handle drags itself,
        // which silently removed any way to move the whole skeleton.
        hitStrokeWidth: VERTEX_HIT_RADIUS,
        name: KEYPOINTS_EDGE_NAME,
      });
      group.add(line);
      edges.push(line);
    }

    const vertices: Konva.Circle[] = [];
    for (const [index, point] of points.entries()) {
      if (states[index] === "hidden") continue;
      const circle = new Konva.Circle({
        x: point.x,
        y: point.y,
        radius: VERTEX_RADIUS,
        stroke: template?.points[index]?.color ?? color,
        strokeWidth: VERTEX_STROKE_WIDTH,
        fill:
          states[index] === "invisible"
            ? INVISIBLE_FILL
            : (template?.points[index]?.color ?? color),
        name: KEYPOINTS_VERTEX_NAME,
        // Handles only on the selected skeleton — a person template has 17
        // points, and live handles everywhere would swallow every click.
        draggable: isSelected,
        // Grabbable well beyond the dot that is drawn — see VERTEX_HIT_RADIUS.
        hitFunc: drawVertexHitArea,
      });
      // The point's own index, not its rank among the drawn circles: hidden
      // points get no circle, so the two diverge as soon as one is hidden.
      circle.setAttr(KEYPOINTS_VERTEX_INDEX_ATTR, index);
      group.add(circle);
      vertices.push(circle);
    }

    this.ctx.annotationLayer.add(group);
    this.nodesById.set(skeleton.id, { group, vertices, edges });
    return true;
  }

  /**
   * Hang each skeleton's label off its highest drawn vertex — the only point of
   * a skeleton that reads as "the top of this shape". Anything lower would put
   * the label inside the figure it names.
   */
  private _followLabel(id: string): void {
    const nodes = this.nodesById.get(id);
    if (!nodes || nodes.vertices.length === 0) return;
    const top = nodes.vertices.reduce((a, b) => (b.y() < a.y() ? b : a));
    this.labels.moveTo(id, { x: top.x() + nodes.group.x(), y: top.y() + nodes.group.y() });
  }

  private _labelEntries(activeIds: ReadonlySet<string>): EntityLabelEntry[] {
    const entries: EntityLabelEntry[] = [];
    for (const skeleton of this.ctx.collection.byKind("keypoints")) {
      const nodes = activeIds.has(skeleton.id) ? this.nodesById.get(skeleton.id) : undefined;
      if (!nodes || nodes.vertices.length === 0) continue;
      const top = nodes.vertices.reduce((a, b) => (b.y() < a.y() ? b : a));
      entries.push({
        id: skeleton.id,
        annotation: skeleton,
        anchor: { x: top.x() + nodes.group.x(), y: top.y() + nodes.group.y() },
      });
    }
    return entries;
  }

  /** Normalized coords → stage pixels, one entry per annotated point. */
  private _toPixels(geometry: KeypointsGeometry, frame: PixelFrame): { x: number; y: number }[] {
    const points: { x: number; y: number }[] = [];
    for (let i = 0; i + 1 < geometry.coords.length; i += 2) {
      points.push({
        x: frame.x + geometry.coords[i] * frame.w,
        y: frame.y + geometry.coords[i + 1] * frame.h,
      });
    }
    return points;
  }

  /**
   * No-op: a skeleton is placed inside this widget by its own tool, which owns
   * its live preview — there is no cross-widget gesture to mirror.
   */
  syncDraft(): void {}

  destroy(): void {
    this.labels.destroy();
    for (const nodes of this.nodesById.values()) nodes.group.destroy();
    this.nodesById.clear();
  }
}

export const keypointsRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "keypoints",
  create: (ctx: Scene2DReadContext) => new KeypointsRenderer2D(ctx),
  createEditor: (ctx) =>
    createFlatCoordsEditor2D<KeypointsGeometry>(ctx, {
      kind: "keypoints",
      idAttr: KEYPOINTS_ID_ATTR,
      vertexName: KEYPOINTS_VERTEX_NAME,
      vertexIndexAttr: KEYPOINTS_VERTEX_INDEX_ATTR,
      readCoords: (geometry) => geometry.coords,
      // `templateId` and `states` are untouched: moving a point changes where
      // it is, never which skeleton it belongs to or whether it is visible.
      withCoords: (geometry, coords) => ({ ...geometry, coords }),
    }),
};
