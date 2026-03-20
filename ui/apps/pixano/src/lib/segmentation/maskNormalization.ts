/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";
import { BaseSchema, type Reference } from "$lib/types/dataset";
import type { CompressedRLEPayload } from "$lib/types/inference";
import { ShapeType, type SaveMaskShape } from "$lib/types/shapeTypes";
import {
  dataUrlToBlob,
  getAlphaBoundingBox,
  rleCountsToBounds,
  rleFrString,
  rleToBitmapCanvas,
} from "$lib/utils/maskUtils";

export interface MaskNormalizationInput {
  mask: CompressedRLEPayload;
  viewRef: Reference;
  itemId: string;
  imageWidth: number;
  imageHeight: number;
}

function normalizeCounts(counts: CompressedRLEPayload["counts"]): number[] {
  return typeof counts === "string" ? rleFrString(counts) : counts;
}

function createBitmapDataUrl(
  counts: number[],
  size: [number, number],
): {
  dataUrl: string;
  blob: Blob | undefined;
  bounds:
    | {
        x: number;
        y: number;
        width: number;
        height: number;
      }
    | undefined;
} {
  const [height, width] = size;
  const bitmapCanvas = rleToBitmapCanvas(counts, size);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return {
      dataUrl: "",
      blob: undefined,
      bounds: rleCountsToBounds(counts, size) ?? undefined,
    };
  }

  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(bitmapCanvas, 0, 0);

  const dataUrl = canvas.toDataURL("image/png");
  return {
    dataUrl,
    blob: dataUrlToBlob(dataUrl) ?? undefined,
    bounds: rleCountsToBounds(counts, size) ?? getAlphaBoundingBox(canvas) ?? undefined,
  };
}

export function normalizeMaskToSaveShape(input: MaskNormalizationInput): SaveMaskShape {
  const normalizedCounts = normalizeCounts(input.mask.counts);
  const height = Number(input.mask.size[0]) || input.imageHeight;
  const width = Number(input.mask.size[1]) || input.imageWidth;
  const size: [number, number] = [height, width];
  const bitmap = createBitmapDataUrl(normalizedCounts, size);

  return {
    status: "saving",
    type: ShapeType.mask,
    viewRef: input.viewRef,
    itemId: input.itemId,
    imageWidth: width,
    imageHeight: height,
    maskDataUrl: bitmap.dataUrl,
    maskBlob: bitmap.blob,
    maskMimeType: "image/png",
    maskBounds: bitmap.bounds,
    rle: {
      counts: normalizedCounts,
      size,
    },
  };
}

export function saveMaskShapeToTrackingOutput(
  shape: SaveMaskShape,
  frameIndex: number,
): MaskSegmentationOutput {
  const timestamp = new Date().toISOString().replace(/Z$/, "+00:00");

  return {
    id: nanoid(10),
    created_at: timestamp,
    updated_at: timestamp,
    table_info: {
      name: "_smart_tracking_preview",
      group: "annotations",
      base_schema: BaseSchema.Mask,
    },
    data: {
      size: shape.rle?.size ?? [shape.imageHeight, shape.imageWidth],
      counts: shape.rle?.counts ?? [shape.imageWidth * shape.imageHeight],
      item_id: shape.itemId,
      view_name: shape.viewRef.name,
      frame_id: shape.viewRef.id,
      frame_index: frameIndex,
      tracklet_id: "",
      entity_dynamic_state_id: "",
      entity_id: "",
      source_type: "pixano",
      source_name: "smart-segmentation",
      source_metadata: "{}",
      inference_metadata: {},
    },
  };
}
