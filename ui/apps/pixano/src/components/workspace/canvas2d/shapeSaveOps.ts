/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference } from "$lib/types/dataset";
import type { Point2D, PolygonOutputMode } from "$lib/types/geometry";
import { ShapeType, type PolygonVertex, type Shape } from "$lib/types/shapeTypes";
import {
  dataUrlToBlob,
  getBoundingBoxFromPolygonPoints,
  type MaskBounds,
} from "$lib/utils/maskUtils";

export interface PolygonSavePayload {
  polygons?: PolygonVertex[][];
  points?: Point2D[];
  outputMode?: PolygonOutputMode;
}

export function toPolygonPoints(
  points: ReadonlyArray<PolygonVertex | Point2D>,
): PolygonVertex[] {
  return points.map((point, index) => ({
    x: point.x,
    y: point.y,
    id: "id" in point ? point.id : index,
  }));
}

export function toClosedPolygonPoints(
  polygons: ReadonlyArray<ReadonlyArray<PolygonVertex | Point2D>>,
): PolygonVertex[][] {
  return polygons.map((polygon) => toPolygonPoints(polygon));
}

export function getSourcePolygons(
  payload: PolygonSavePayload,
): Array<Array<PolygonVertex | Point2D>> {
  if (Array.isArray(payload.polygons) && payload.polygons.length > 0) {
    return payload.polygons;
  }

  if (Array.isArray(payload.points) && payload.points.length > 0) {
    return [payload.points.map((point) => ({ x: point.x, y: point.y }))];
  }

  return [];
}

function rasterizePolygonsToMask(
  polygons: PolygonVertex[][],
  imageWidth: number,
  imageHeight: number,
): {
  dataUrl: string;
  blob: Blob | null;
  mimeType: string;
  bounds: MaskBounds | null;
} {
  const canvas = document.createElement("canvas");
  canvas.width = imageWidth;
  canvas.height = imageHeight;
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return {
      dataUrl: "",
      blob: null,
      mimeType: "image/png",
      bounds: null,
    };
  }

  ctx.clearRect(0, 0, imageWidth, imageHeight);
  ctx.fillStyle = "white";

  for (const polygon of polygons) {
    if (polygon.length < 3) continue;
    ctx.beginPath();
    ctx.moveTo(polygon[0].x, polygon[0].y);
    for (let i = 1; i < polygon.length; i += 1) {
      ctx.lineTo(polygon[i].x, polygon[i].y);
    }
    ctx.closePath();
    ctx.fill();
  }

  const dataUrl = canvas.toDataURL("image/png");
  const blob = dataUrlToBlob(dataUrl);
  const bounds = getBoundingBoxFromPolygonPoints(polygons);

  return {
    dataUrl,
    blob,
    mimeType: "image/png",
    bounds,
  };
}

export function buildRectangleSaveShape(
  geometry: { x: number; y: number; width: number; height: number },
  localDraftShape: Shape | null,
  viewRef: Reference,
  selectedItemId: string,
  currentImage: HTMLImageElement | ImageBitmap | undefined,
): Shape | null {
  // Prefer the current local draft geometry (updated by Transformer/drag) over FSM's stale geometry
  let finalGeo = geometry;
  if (localDraftShape?.status === "creating" && localDraftShape.type === ShapeType.bbox) {
    const shape = localDraftShape;
    const w = shape.width < 0 ? -shape.width : shape.width;
    const h = shape.height < 0 ? -shape.height : shape.height;
    const x = shape.width < 0 ? shape.x + shape.width : shape.x;
    const y = shape.height < 0 ? shape.y + shape.height : shape.y;
    finalGeo = { x, y, width: w, height: h };
  }

  if (!currentImage) return null;

  return {
    status: "saving",
    attrs: {
      x: finalGeo.x,
      y: finalGeo.y,
      width: finalGeo.width,
      height: finalGeo.height,
    },
    type: ShapeType.bbox,
    viewRef,
    itemId: selectedItemId,
    imageWidth: currentImage.width,
    imageHeight: currentImage.height,
  };
}

export function buildPolygonSaveShape(
  payload: PolygonSavePayload,
  viewRef: Reference,
  selectedItemId: string,
  currentImage: HTMLImageElement | ImageBitmap | undefined,
  selectedToolOutputMode: PolygonOutputMode,
): Shape | null {
  const sourcePolygons = getSourcePolygons(payload);
  if (sourcePolygons.length === 0) return null;
  if (!currentImage) return null;

  const polygonMode: PolygonOutputMode = payload.outputMode ?? selectedToolOutputMode;
  const polygonPoints = sourcePolygons
    .map((polygon) =>
      polygon.map((point, id) => ({
        x: polygonMode === "mask" ? Math.round(point.x) : point.x,
        y: polygonMode === "mask" ? Math.round(point.y) : point.y,
        id: "id" in point ? point.id : id,
      })),
    )
    .filter((polygon) => polygon.length >= 3);
  if (polygonPoints.length === 0) return null;

  const bitmap = rasterizePolygonsToMask(polygonPoints, currentImage.width, currentImage.height);

  if (polygonMode === "mask") {
    return {
      status: "saving",
      type: ShapeType.mask,
      maskDataUrl: bitmap.dataUrl,
      maskMimeType: bitmap.mimeType,
      maskBlob: bitmap.blob ?? undefined,
      maskBounds: bitmap.bounds ?? undefined,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
      polygonMode,
      polygonPoints,
    };
  }

  return {
    status: "saving",
    type: ShapeType.polygon,
    polygonMode,
    polygonPoints,
    maskDataUrl: bitmap.dataUrl,
    maskMimeType: bitmap.mimeType,
    maskBlob: bitmap.blob ?? undefined,
    maskBounds: bitmap.bounds ?? undefined,
    viewRef,
    itemId: selectedItemId,
    imageWidth: currentImage.width,
    imageHeight: currentImage.height,
  };
}
