/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Matrix3, Matrix4, Vector3, Vector4 } from "three";

import type { LocalBBox3DAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
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
 * Renders the "bbox3d" kind on the Konva scene: one rect (+ optional entity
 * label) per annotation, a shared transformer for the selection, and the
 * drag/transform handlers that write geometry changes back through the
 * collection and the mutation queue.
 */
class BBox3DRenderer2D implements AnnotationRenderer2D {
  readonly kind = "bbox3d" as const;

  private readonly boxByBBoxId = new Map<string, Konva.Line[]>();
  private readonly labelByBBoxId = new Map<string, Konva.Label>();
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
      activeIds.add(bbox.id);
      let projectedBox = this.boxByBBoxId.get(bbox.id);
      if (!projectedBox) {
        const newBox = this._makeProjectedBox(bbox, frame);
        if (!newBox) continue;
        newBox.forEach(line => this.ctx.annotationLayer.add(line));
        this.boxByBBoxId.set(bbox.id, newBox);
        projectedBox = newBox;
      } else if (frame) {
        this._updateProjectedBox(projectedBox, bbox, frame);
      }
    }

    for (const [id, projectedbbox] of this.boxByBBoxId) {
      if (!activeIds.has(id)) { projectedbbox.forEach(line => line.destroy()); this.boxByBBoxId.delete(id); }
    }

    this._syncTransformer();
    this.ctx.annotationLayer.batchDraw();
  }

  destroy(): void {
    this.transformer.destroy();
    for (const projectedBox of this.boxByBBoxId.values()) {
      for (const line of projectedBox) {
        line.destroy();
      }
    }
    this.boxByBBoxId.clear();
    for (const label of this.labelByBBoxId.values()) label.destroy();
    this.labelByBBoxId.clear();
  }

  private _syncTransformer(): void {
    const id = this.ctx.collection.selectedId;
    const projectedBox = id ? this.boxByBBoxId.get(id) : undefined;
    if (projectedBox) {
      for (const line of projectedBox) {
          this.transformer.nodes([line]);
      }
      this.transformer.moveToTop();
    } else {
      this.transformer.nodes([]);
    }
    this.transformer.getLayer()?.batchDraw();
  }

  private _makeLine(p1: { x: number; y: number }, p2: { x: number; y: number }): Konva.Line {
    const line = new Konva.Line({
      points: [p1.x, p1.y, p2.x, p2.y],
      stroke: "#f59e0b",
      strokeWidth: 2,
    });
    return line;
  }

  private _get3dbboxCorners(bbox: LocalBBox3DAnnotation): { x: number; y: number; z: number }[] {
    const [x, y, z, w, h, d] = bbox.geometry.coords;
    let rotation_matrix;
    if (!bbox.geometry.rotation){
      rotation_matrix = new Matrix3().identity();
    }else{
      rotation_matrix = new Matrix3().fromArray(bbox.geometry.rotation).transpose();
    }
    const unitCube = [
      [-0.5,-0.5, -0.5],
      [0.5, -0.5, -0.5],
      [0.5, 0.5, -0.5],
      [-0.5, 0.5, -0.5],
      [-0.5, -0.5, 0.5],
      [0.5, -0.5, 0.5],
      [0.5, 0.5, 0.5],
      [-0.5, 0.5, 0.5],
    ]
    let scaledCorners = unitCube.map(([cx, cy, cz]) => [cx * w, cy * h, cz * d]);
    let rotatedCorners = scaledCorners.map(([cx, cy, cz]) => (new Vector3(cx, cy, cz)).applyMatrix3(rotation_matrix));
    let translatedCorners = rotatedCorners.map((corner) => ({ x: corner.x + x, y: corner.y + y, z: corner.z + z }));
    return translatedCorners;
  }

  private _projectPoint(bbox: LocalBBox3DAnnotation): { x: number; y: number }[] | null {
    if (!this.ctx.camera.calibration) return null;
    const f = this.ctx.camera.calibration.f;
    const c = this.ctx.camera.calibration.c;
    const extrinsics = new Matrix4().fromArray(this.ctx.camera.calibration.extrinsicMatrix).transpose();
    // Homogenous points
    let points_h = this._get3dbboxCorners(bbox).map(point => [point.x, point.y, point.z, 1]);
    // world -> cam
    let pointsCam = points_h.map(([x, y, z, w]) => {
      let vec = new Vector4(x, y, z, w).applyMatrix4(extrinsics);
      return { x: vec.x, y: vec.y, z: vec.z };
    });
    let projectedPoints = pointsCam.map(({x, y, z}) => {
      if (z <= 0) return null; // Behind the camera
      return {
        x: f[0] * x / z + c[0],
        y: f[1] * y / z + c[1],
      };
    });
    return projectedPoints.every(p => p !== null) ? projectedPoints as { x: number; y: number }[] : null;
  }

  private _makeProjectedBox(bbox: LocalBBox3DAnnotation, frame: PixelFrame | null): Konva.Line[] | null {
    if (!frame) return null;
    const edges = [
      [0, 1], [1, 2], [2, 3], [3, 0],
      [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
      [2, 5], [1, 6]
    ];
    const pixels = this._getNormalizedProjectedPoints(bbox, frame);
    let lines = [];
        for (const [a, b] of edges) {
          if (pixels?.[a] && pixels?.[b]) {
            const konvaLine = this._makeLine(pixels[a], pixels[b]);
            lines.push(konvaLine);
          }
        }
    return lines;
  }

  private _updateProjectedBox(lines: Konva.Line[], bbox: LocalBBox3DAnnotation, frame: PixelFrame): void {
    if (!frame) return;
    const edges = [
      [0, 1], [1, 2], [2, 3], [3, 0],
      [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
      [2, 5], [1, 6]
    ];
    const pixels = this._getNormalizedProjectedPoints(bbox,frame);
    if (pixels) {
      for (let i = 0; i<edges.length; i++){
        const p1 = pixels[edges[i][0]];
        const p2 = pixels[edges[i][1]];

        if (!p1 || !p2) continue;
        lines[i].points([p1.x, p1.y, p2.x, p2.y]);

      }
    }
  }

  private _getNormalizedProjectedPoints(bbox: LocalBBox3DAnnotation, frame: PixelFrame): ({ x: number; y: number } | null)[] {
    let projectedPoints = this._projectPoint(bbox);
    let normalizedPoints = projectedPoints?.map(point => {
          const dx = point.x /this.ctx.camera.imageWidth;
          const dy = point.y /this.ctx.camera.imageHeight;
          return {x:dx,y:dy};
          });
    const pixels = normalizedPoints?.map(point => normalizedPointToPixel(point.x, point.y, frame));
    if (!pixels) return [];
    return pixels;
    }
}

export const bbox3dRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "bbox3d",
  create: (ctx: Scene2DReadContext) => new BBox3DRenderer2D(ctx),
};
