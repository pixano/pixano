/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";
import { nanoid } from "nanoid";

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

export interface TrackingMaskSourceInput {
  modelName?: string | null;
  providerName?: string | null;
}

export interface TrackingMaskSourceFields {
  source_type: "model";
  source_name: string;
  source_metadata: string;
}

const DEFAULT_TRACKING_SOURCE_NAME = "smart-segmentation";

function normalizeCounts(counts: CompressedRLEPayload["counts"]): number[] {
  return typeof counts === "string" ? rleFrString(counts) : counts;
}

function cloneMaskCounts(counts: number[] | string): number[] | string {
  return Array.isArray(counts) ? [...counts] : counts;
}

function cloneMaskSize(size: number[]): number[] {
  return [...size];
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseProviderName(sourceMetadata: unknown): string | null {
  if (!isNonEmptyString(sourceMetadata)) {
    return null;
  }

  try {
    const parsed = JSON.parse(sourceMetadata) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      "provider_name" in parsed &&
      isNonEmptyString((parsed as { provider_name?: unknown }).provider_name)
    ) {
      return (parsed as { provider_name: string }).provider_name;
    }
  } catch {
    return null;
  }

  return null;
}

export function buildTrackingMaskSourceFields(
  source?: TrackingMaskSourceInput,
): TrackingMaskSourceFields {
  const sourceName =
    source?.modelName && source.modelName.trim().length > 0
      ? source.modelName
      : DEFAULT_TRACKING_SOURCE_NAME;
  const sourceMetadata =
    source?.providerName && source.providerName.trim().length > 0
      ? JSON.stringify({ provider_name: source.providerName })
      : "{}";

  return {
    source_type: "model",
    source_name: sourceName,
    source_metadata: sourceMetadata,
  };
}

export function normalizeTrackingMaskSourceFields(
  source:
    | {
        source_type?: unknown;
        source_name?: unknown;
        source_metadata?: unknown;
      }
    | null
    | undefined,
  fallback?: TrackingMaskSourceInput,
): TrackingMaskSourceFields {
  const sourceIsModel = source?.source_type === "model";
  const providerName = fallback?.providerName ?? parseProviderName(source?.source_metadata);
  const modelName =
    fallback?.modelName ??
    (sourceIsModel && isNonEmptyString(source?.source_name)
      ? source.source_name
      : DEFAULT_TRACKING_SOURCE_NAME);

  return buildTrackingMaskSourceFields({
    modelName,
    providerName,
  });
}

export function normalizeTrackingMaskOutputForPersistence(
  output: MaskSegmentationOutput,
  fallback?: TrackingMaskSourceInput,
): MaskSegmentationOutput {
  const clonedOutput = cloneTrackingMaskOutput(output);
  return {
    ...clonedOutput,
    data: {
      ...clonedOutput.data,
      ...normalizeTrackingMaskSourceFields(clonedOutput.data, fallback),
    },
  };
}

export function cloneTrackingMaskOutput(output: MaskSegmentationOutput): MaskSegmentationOutput {
  return {
    ...output,
    data: {
      ...output.data,
      size: cloneMaskSize(output.data.size),
      counts: cloneMaskCounts(output.data.counts),
    },
  };
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
  const normalizedCounts = [...normalizeCounts(input.mask.counts)];
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
      size: [...size] as [number, number],
    },
  };
}

export function saveMaskShapeToTrackingOutput(
  shape: SaveMaskShape,
  frameIndex: number,
  source?: TrackingMaskSourceInput,
): MaskSegmentationOutput {
  const timestamp = new Date().toISOString().replace(/Z$/, "+00:00");
  const sourceFields = buildTrackingMaskSourceFields(source);

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
      size: cloneMaskSize(shape.rle?.size ?? [shape.imageHeight, shape.imageWidth]),
      counts: cloneMaskCounts(shape.rle?.counts ?? [shape.imageWidth * shape.imageHeight]),
      item_id: shape.itemId,
      view_name: shape.viewRef.name,
      frame_id: shape.viewRef.id,
      frame_index: frameIndex,
      tracklet_id: "",
      entity_dynamic_state_id: "",
      entity_id: "",
      source_type: sourceFields.source_type,
      source_name: sourceFields.source_name,
      source_metadata: sourceFields.source_metadata,
      inference_metadata: {},
    },
  };
}
