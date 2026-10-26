/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import type { AnnotationKind } from "../annotationCollection.svelte.js";
import { commitGeometryEdit } from "../payloadBuilders.js";
import type { AnnotationEditor2D } from "./renderer.js";
import { clampUnit, getPixelFrame, pixelPointToNormalized } from "./scene2dGeometry.js";
import type { Scene2DContext, StagedWorkFlag } from "./sceneContext.js";

/**
 * What a kind must tell this editor to be editable: how its nodes are labelled,
 * and how to read/write the flat coordinate list inside its geometry.
 */
export interface FlatCoordsEditorSpec<G> {
  kind: AnnotationKind;
  /** Konva attr carrying the local annotation id, stamped on the group. */
  idAttr: string;
  /** Konva `name` of a draggable vertex handle. */
  vertexName: string;
  /** Konva attr carrying a vertex's index into the *point* list. */
  vertexIndexAttr: string;
  /**
   * Konva attr this editor sets on a shape's group while the shape is dragged,
   * whole or by one vertex. The kind's renderer leaves a group so marked alone:
   * rebuilt under the pointer, the drag would be cut short.
   */
  draggingAttr: string;
  /** Flat `[x0, y0, x1, y1, …]`, normalized. */
  readCoords: (geometry: G) => number[];
  /** Rebuild the geometry around a new coordinate list, preserving the rest. */
  withCoords: (geometry: G, coords: number[]) => G;
}

/**
 * Editing input for every kind whose geometry is a flat list of normalized
 * points — keypoint skeletons and multi-path rings today.
 *
 * Two gestures, both ending in one `commitGeometryEdit`:
 *
 * - drag a **vertex** handle → that single point moves;
 * - drag the **shape** anywhere else → every point shifts by the same delta.
 *
 * Shared rather than copied per kind because the parts that would be duplicated
 * are the ones that must not drift: reading the drag off the node, converting
 * pixels back to normalized coordinates, resetting the group offset after a
 * translation, and holding the drag while it runs. A kind supplies only its
 * node labels and how to swap the coordinate list into its own geometry shape.
 *
 * A drag is work of its own until it ends: the move sits on the nodes, not in
 * the collection. So the editor raises its staged-work flag while one runs —
 * the record counts it as one unsaved item, and Discard or a delete pressed
 * mid-drag drops it — and stamps the shape's group (`spec.draggingAttr`) so that
 * the renderer's sync leaves it alone instead of rebuilding it under the
 * pointer. The drag commits onto the shape's row, by its id, when it ends. It
 * commits only a drag it saw begin.
 *
 * Like `bboxEditor2D`, it never creates nodes — the renderer owns those (D4) —
 * and it listens at the **layer**, so display and input stay decoupled. It only
 * has to survive its own namespace: handlers are registered as
 * `dragstart.<kind>-edit` and `dragend.<kind>-edit` so `destroy()` removes
 * exactly these.
 */
class FlatCoordsEditor2D<G> implements AnnotationEditor2D {
  readonly kind: AnnotationKind;

  private readonly dragStartEvent: string;
  private readonly dragEndEvent: string;
  /** Raised while a drag runs. */
  private readonly staged: StagedWorkFlag | undefined;
  /** The group of each shape being dragged, to the node Konva drags: the group, or a vertex. */
  private readonly dragging = new Map<Konva.Node, Konva.Node>();

  constructor(
    private readonly ctx: Scene2DContext,
    private readonly spec: FlatCoordsEditorSpec<G>,
  ) {
    this.kind = spec.kind;
    this.dragStartEvent = `dragstart.${spec.kind}-edit`;
    this.dragEndEvent = `dragend.${spec.kind}-edit`;
    this.staged = ctx.claimStagedWork?.(() => this._abandonDrags());
    // A drag's start and end bubble up from the node, so the layer hears them
    // for every group and vertex without the editor owning node creation.
    ctx.annotationLayer.on(this.dragStartEvent, (e) => this._startDrag(e.target));
    ctx.annotationLayer.on(this.dragEndEvent, (e) => this._endDrag(e.target));
  }

  /**
   * Nothing to attach: the handles are the renderer's own vertex nodes, so
   * there is no transformer to move onto the selection. Selection still governs
   * editing — the renderer only draws handles for the selected annotation.
   */
  syncSelection(): void {}

  destroy(): void {
    this.ctx.annotationLayer.off(`${this.dragStartEvent} ${this.dragEndEvent}`);
    // A drag cut short with the editor can no longer be confirmed.
    this._releaseDragging();
    this.staged?.set(false);
  }

  /** The group of the shape a dragged node belongs to: the node itself, or a vertex's parent. */
  private _groupOf(node: Konva.Node): Konva.Node | null {
    const group = node.name() === this.spec.vertexName ? node.getParent() : node;
    return group?.getAttr(this.spec.idAttr) ? group : null;
  }

  /** A drag of a shape begins: hold the shape, and the flag, until the drag ends. */
  private _startDrag(node: Konva.Node): void {
    const group = this._groupOf(node);
    if (!group) return;
    this.dragging.set(group, node);
    group.setAttr(this.spec.draggingAttr, true);
    this._updateStaged();
  }

  /** A drag ends: commit the shape where it was let go. */
  private _endDrag(node: Konva.Node): void {
    const group = this._groupOf(node);
    // A drag Discard dropped ends here too, as Konva stops it: nothing to commit.
    if (!group || !this.dragging.delete(group)) return;
    // Let go first: the commit redraws, and the renderer must then rebuild the
    // shape where the move put it.
    group.setAttr(this.spec.draggingAttr, false);
    this._commitDrag(node, group);
    // The renderer left the shape alone while it was held, whatever changed
    // meanwhile — a save ending, the selection cleared — and a drag ending
    // where it began commits nothing: draw it as it now stands either way.
    this.ctx.requestRedraw();
    this._updateStaged();
  }

  /**
   * Discard: the running drags are dropped, and their shapes drawn again as the
   * collection holds them.
   */
  private _abandonDrags(): void {
    const abandoned = this._releaseDragging();
    this._updateStaged();
    // Konva ends each as a release would, which reaches `_endDrag` with no shape held.
    for (const node of abandoned.values()) if (node.isDragging()) node.stopDrag();
    if (abandoned.size > 0) this.ctx.requestRedraw();
  }

  /**
   * Raise the flag while a drag runs, lower it once none does. Called as a
   * drag starts and ends, never as the pointer moves.
   */
  private _updateStaged(): void {
    this.staged?.set(this.dragging.size > 0);
  }

  /** Let go of the shapes being dragged, and return their groups with the node each drag holds. */
  private _releaseDragging(): Map<Konva.Node, Konva.Node> {
    const released = new Map(this.dragging);
    this.dragging.clear();
    for (const group of released.keys()) group.setAttr(this.spec.draggingAttr, false);
    return released;
  }

  /** Read a drag of `node`, a vertex of `group` or `group` itself, back into the coordinates. */
  private _commitDrag(node: Konva.Node, group: Konva.Node): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    const id = group.getAttr(this.spec.idAttr) as string | undefined;
    const annotation = id ? this.ctx.collection.find(id) : undefined;
    if (!id || !annotation) return;
    const coords = [...this.spec.readCoords(annotation.geometry as G)];

    const isVertex = node !== group;
    if (isVertex) {
      const index = node.getAttr(this.spec.vertexIndexAttr) as number | undefined;
      if (index === undefined || index * 2 + 1 >= coords.length) return;
      // The handle carries the group's offset too, since it is a child of it.
      const point = pixelPointToNormalized(node.x() + group.x(), node.y() + group.y(), frame);
      coords[index * 2] = point.x;
      coords[index * 2 + 1] = point.y;
    } else {
      // A group drag leaves the shape's own coordinates untouched and records
      // the move as a group offset. Bake that offset into every point, then
      // zero it — otherwise the next resync would draw the shape twice-shifted.
      const dx = group.x() / frame.w;
      const dy = group.y() / frame.h;
      if (dx === 0 && dy === 0) return;
      for (let i = 0; i + 1 < coords.length; i += 2) {
        coords[i] = clampUnit(coords[i] + dx);
        coords[i + 1] = clampUnit(coords[i + 1] + dy);
      }
      group.x(0);
      group.y(0);
    }

    commitGeometryEdit(this.ctx, id, this.spec.withCoords(annotation.geometry as G, coords));
  }
}

export function createFlatCoordsEditor2D<G>(
  ctx: Scene2DContext,
  spec: FlatCoordsEditorSpec<G>,
): AnnotationEditor2D {
  return new FlatCoordsEditor2D(ctx, spec);
}
