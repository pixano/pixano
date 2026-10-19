/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SaveMaskShape } from "$lib/types/shapeTypes";
import { resolveMaskBitmapSource, resolveMaskBounds } from "$lib/utils/maskUtils";

/** The fields of a mask its drawing depends on. */
export interface FingerprintMask {
  readonly id: string;
  readonly data: Record<string, unknown> & { readonly inference_metadata?: unknown };
  readonly ui: {
    readonly bitmapUrl?: string;
    readonly bounds?: { x: number; y: number; width: number; height: number } | null;
    readonly bitmapCanvas?: unknown;
    readonly displayControl: { readonly hidden: boolean; readonly highlighted: string };
  };
}

/**
 * A string that changes whenever the mask layer must be redrawn: the image size, each mask's
 * pixels, bounds, color and display state, and the preview. Colors are the resolved ones, so a
 * change of color mode or palette repaints the masks, and a resolver change that keeps every
 * color does not.
 */
export function buildMaskFingerprint(input: {
  imageWidth: number;
  imageHeight: number;
  forceNeutral: boolean;
  masks: readonly FingerprintMask[];
  colorById: ReadonlyMap<string, string>;
  preview: SaveMaskShape | null;
}): string {
  const { masks, colorById, preview } = input;
  let fingerprint = `${input.imageWidth}x${input.imageHeight}|neutral:${input.forceNeutral}|`;
  for (const mask of masks) {
    const source =
      mask.ui.bitmapUrl ??
      resolveMaskBitmapSource({ data: mask.data, metadata: mask.data.inference_metadata }) ??
      "";
    const bounds =
      mask.ui.bounds ??
      resolveMaskBounds({ data: mask.data, metadata: mask.data.inference_metadata });
    const hasCanvas = mask.ui.bitmapCanvas ? "C" : "";
    const color = colorById.get(mask.id) ?? "";
    fingerprint += `${mask.id}:${hasCanvas}${source}:${bounds?.x ?? 0},${bounds?.y ?? 0},${bounds?.width ?? 0},${bounds?.height ?? 0}:${color}:${mask.ui.displayControl.hidden}:${mask.ui.displayControl.highlighted};`;
  }
  if (preview?.rle) {
    const previewCounts = Array.isArray(preview.rle.counts)
      ? preview.rle.counts.length
      : preview.rle.counts;
    fingerprint += `preview:${preview.viewRef.id}:${previewCounts}:${preview.maskBounds?.x ?? 0},${preview.maskBounds?.y ?? 0},${preview.maskBounds?.width ?? 0},${preview.maskBounds?.height ?? 0};`;
  }
  return fingerprint;
}
