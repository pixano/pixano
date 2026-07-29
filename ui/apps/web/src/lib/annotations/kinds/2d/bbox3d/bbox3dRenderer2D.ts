/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Matrix3, Matrix4, Vector3, Vector4 } from "three";

import type { BBox3DGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";
import {
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  normalizedPointToPixel,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";

/**
 * Corner pairs of the projected wireframe: the cube's 12 edges plus the two
 * front-face diagonals that mark the box's facing direction. Corner order
 * matches `_get3dbboxCorners` (bottom face 0-3, top face 4-7).
 */
const BOX_EDGES: readonly (readonly [number, number])[] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 0],
  [4, 5],
  [5, 6],
  [6, 7],
  [7, 4],
  [0, 4],
  [1, 5],
  [2, 6],
  [3, 7],
  [2, 5],
  [1, 6],
];

const PROJECTED_EDGE_COLOR = "#f59e0b";
const PROJECTED_EDGE_WIDTH = 2;

/**
 * Renders the "bbox3d" kind on the Konva scene: each 3D box is projected
 * through the widget's camera calibration into a wireframe of `BOX_EDGES`
 * lines, plus a shared transformer for the selection. Each box always owns its
 * full set of lines; a projection that fails (missing calibration, or a corner
 * behind the camera) hides them rather than leaving stale geometry.
 */
class BBox3DRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox3d" as const;

  private readonly boxByBBoxId = new Map<string, Konva.Line[]>();
  private readonly transformer: Konva.Transformer;

  constructor(private readonly ctx: Scene2DReadContext) {
    this.transformer = new Konva.Transformer({
      rotateEnabled: false,
      anchorStroke: BBOX_COLOR_PERSISTED,
      anchorFill: "#0f172a",
      borderStroke: BBOX_COLOR_PERSISTED,
      keepRatio: false,
      ignoreStroke: true,
    });
    ctx.annotationLayer.add(this.transformer);
  }

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    for (const bbox of this.ctx.collection.byKind("bbox3d")) {
      // Entity-driven visibility, mirroring the 2D bbox renderer: a persisted
      // box whose entity is hidden gets no lines. Drafts are always shown.
      if (bbox.persisted && !this.ctx.isEntityVisible(bbox.entityId)) continue;
      activeIds.add(bbox.id);
      let projectedBox = this.boxByBBoxId.get(bbox.id);
      if (!projectedBox && frame) {
        projectedBox = this._makeProjectedBox();
        for (const line of projectedBox) this.ctx.annotationLayer.add(line);
        this.boxByBBoxId.set(bbox.id, projectedBox);
      }
      if (projectedBox && frame) this._applyProjection(projectedBox, bbox.geometry, frame);
    }

    for (const [id, projectedBox] of this.boxByBBoxId) {
      if (!activeIds.has(id)) {
        for (const line of projectedBox) line.destroy();
        this.boxByBBoxId.delete(id);
      }
    }

    this._syncTransformer();
    this.ctx.annotationLayer.batchDraw();
  }

  destroy(): void {
    this.transformer.destroy();
    for (const projectedBox of this.boxByBBoxId.values()) {
      for (const line of projectedBox) line.destroy();
    }
    this.boxByBBoxId.clear();
  }

  private _syncTransformer(): void {
    const id = this.ctx.collection.selectedId;
    const projectedBox = id ? this.boxByBBoxId.get(id) : undefined;
    if (projectedBox) {
      this.transformer.nodes(projectedBox);
      this.transformer.moveToTop();
    } else {
      this.transformer.nodes([]);
    }
    this.transformer.getLayer()?.batchDraw();
  }

  /** One hidden line per `BOX_EDGES` entry; `_applyProjection` fills them in. */
  private _makeProjectedBox(dash?: number[]): Konva.Line[] {
    return BOX_EDGES.map(
      () =>
        new Konva.Line({
          points: [],
          stroke: PROJECTED_EDGE_COLOR,
          strokeWidth: PROJECTED_EDGE_WIDTH,
          visible: false,
          dash,
        }),
    );
  }

  /**
   * Project the geometry and update every wireframe line, or hide them all
   * when the projection fails (no calibration / a corner behind the camera) —
   * lines must never keep stale points, since a box can cross the camera
   * plane between two syncs.
   */
  private _applyProjection(lines: Konva.Line[], geometry: BBox3DGeometry, frame: PixelFrame): void {
    const pixels = this._getProjectedPixels(geometry, frame);
    if (!pixels) {
      for (const line of lines) line.visible(false);
      return;
    }
    for (let i = 0; i < BOX_EDGES.length; i++) {
      const [a, b] = BOX_EDGES[i];
      lines[i].points([pixels[a].x, pixels[a].y, pixels[b].x, pixels[b].y]);
      lines[i].visible(true);
    }
  }

  /** The box's 8 corners in world (Lance, Z-up) space. */
  private _get3dbboxCorners(geometry: BBox3DGeometry): { x: number; y: number; z: number }[] {
    const [x, y, z, w, h, d] = geometry.coords;
    const rotationMatrix = geometry.rotation
      ? new Matrix3().fromArray(geometry.rotation).transpose()
      : new Matrix3().identity();
    const unitCube = [
      [-0.5, -0.5, -0.5],
      [0.5, -0.5, -0.5],
      [0.5, 0.5, -0.5],
      [-0.5, 0.5, -0.5],
      [-0.5, -0.5, 0.5],
      [0.5, -0.5, 0.5],
      [0.5, 0.5, 0.5],
      [-0.5, 0.5, 0.5],
    ];
    return unitCube.map(([cx, cy, cz]) => {
      const corner = new Vector3(cx * w, cy * h, cz * d).applyMatrix3(rotationMatrix);
      return { x: corner.x + x, y: corner.y + y, z: corner.z + z };
    });
  }

  /**
   * Pinhole-project the corners into image pixel coordinates, or null when the
   * widget has no calibration or any corner sits behind the camera.
   */
  private _projectCorners(geometry: BBox3DGeometry): { x: number; y: number }[] | null {
    const calibration = this.ctx.camera.calibration;
    if (!calibration) return null;
    const { f, c } = calibration;
    const extrinsics = new Matrix4().fromArray(calibration.extrinsicMatrix).transpose();
    const projected: { x: number; y: number }[] = [];
    for (const corner of this._get3dbboxCorners(geometry)) {
      // world -> camera
      const cam = new Vector4(corner.x, corner.y, corner.z, 1).applyMatrix4(extrinsics);
      if (cam.z <= 0) return null; // Behind the camera
      projected.push({
        x: (f[0] * cam.x) / cam.z + c[0],
        y: (f[1] * cam.y) / cam.z + c[1],
      });
    }
    return projected;
  }

  /** Corner pixels in Konva stage space, or null when projection fails. */
  private _getProjectedPixels(
    geometry: BBox3DGeometry,
    frame: PixelFrame,
  ): { x: number; y: number }[] | null {
    const projected = this._projectCorners(geometry);
    if (!projected) return null;
    const pixels: { x: number; y: number }[] = [];
    for (const point of projected) {
      const pixel = normalizedPointToPixel(
        point.x / this.ctx.camera.imageWidth,
        point.y / this.ctx.camera.imageHeight,
        frame,
      );
      if (!pixel) return null;
      pixels.push(pixel);
    }
    return pixels;
  }
}

export const bbox3dRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "bbox3d",
  create: (ctx: Scene2DReadContext) => new BBox3DRenderer2D(ctx),
};
