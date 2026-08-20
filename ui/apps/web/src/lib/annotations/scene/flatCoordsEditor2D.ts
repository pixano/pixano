/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import type { AnnotationKind } from "../annotationCollection.svelte.js";
import { commitGeometryEdit } from "../payloadBuilders.js";
import type { AnnotationEditor2D } from "./renderer.js";
import { getPixelFrame, pixelPointToNormalized } from "./scene2dGeometry.js";
import type { Scene2DContext } from "./sceneContext.js";

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
 * pixels back to normalized coordinates, and resetting the group offset after a
 * translation. A kind supplies only its node labels and how to swap the
 * coordinate list into its own geometry shape.
 *
 * Like `bboxEditor2D`, it never creates nodes — the renderer owns those (D4) —
 * and it listens at the **layer**, so display and input stay decoupled. It only
 * has to survive its own namespace: handlers are registered as
 * `dragend.<kind>-edit` so `destroy()` removes exactly these.
 */
class FlatCoordsEditor2D<G> implements AnnotationEditor2D {
  readonly kind: AnnotationKind;

  private readonly dragEndEvent: string;

  constructor(
    private readonly ctx: Scene2DContext,
    private readonly spec: FlatCoordsEditorSpec<G>,
  ) {
    this.kind = spec.kind;
    this.dragEndEvent = `dragend.${spec.kind}-edit`;
    ctx.annotationLayer.on(this.dragEndEvent, (e) => this._onDragEnd(e.target));
  }

  /**
   * Nothing to attach: the handles are the renderer's own vertex nodes, so
   * there is no transformer to move onto the selection. Selection still governs
   * editing — the renderer only draws handles for the selected annotation.
   */
  syncSelection(): void {}

  destroy(): void {
    this.ctx.annotationLayer.off(this.dragEndEvent);
  }

  private _onDragEnd(node: Konva.Node): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    const isVertex = node.name() === this.spec.vertexName;
    const group = (isVertex ? node.getParent() : node) as Konva.Node | null;
    const id = group?.getAttr(this.spec.idAttr) as string | undefined;
    if (!group || !id) return;

    const annotation = this.ctx.collection.find(id);
    if (!annotation) return;
    const coords = [...this.spec.readCoords(annotation.geometry as G)];

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
    this.ctx.requestRedraw();
  }
}

function clampUnit(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function createFlatCoordsEditor2D<G>(
  ctx: Scene2DContext,
  spec: FlatCoordsEditorSpec<G>,
): AnnotationEditor2D {
  return new FlatCoordsEditor2D(ctx, spec);
}
