/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Decode a compressed RLE string into a numeric counts array.
 * This is the inverse of `rleToString` — the primary deserialization path
 * for mask data received from the backend.
 */
export function rleFrString(s: string): number[] {
  const cnts: number[] = [];
  let p = 0;
  while (p < s.length) {
    let x = 0;
    let k = 0;
    let more = true;
    while (more) {
      const c = s.charCodeAt(p) - 48;
      x |= (c & 0x1f) << (5 * k);
      more = (c & 0x20) !== 0;
      p += 1;
      k += 1;
      if (!more && c & 0x10) {
        x |= -1 << (5 * k);
      }
    }
    if (cnts.length > 2) {
      x += cnts[cnts.length - 2];
    }
    cnts.push(x);
  }
  return cnts;
}

/**
 * Encode a numeric counts array into a compressed RLE string.
 * Used when saving masks back to the backend.
 */
export function rleToString(cnts: number[]): string {
  let s = "";
  for (let i = 0; i < cnts.length; i++) {
    let x = cnts[i];
    if (i > 2) {
      x -= cnts[i - 2];
    }
    let more = true;
    while (more) {
      let c = x & 0x1f;
      x >>= 5;
      more = c & 0x10 ? x !== -1 : x !== 0;
      if (more) c |= 0x20;
      s += String.fromCharCode(c + 48);
    }
  }
  return s;
}

/**
 * Decode an uncompressed RLE counts array to an alpha-mask OffscreenCanvas.
 * Column-major (Fortran) order: iterate column by column.
 * White pixels (255,255,255,255) where mask=1, transparent where mask=0.
 * Returns an OffscreenCanvas — avoids the expensive toDataURL() roundtrip.
 */
export function rleToBitmapCanvas(
  counts: number[],
  size: [number, number],
): OffscreenCanvas {
  const [h, w] = size;
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Failed to get 2d context from OffscreenCanvas");
  const imageData = ctx.createImageData(w, h);
  const data = imageData.data;

  // Decode RLE in column-major order
  let idx = 0;
  let pixel = 0; // 0 = background, 1 = foreground (alternates)
  for (const count of counts) {
    for (let j = 0; j < count; j++) {
      if (pixel === 1) {
        const col = Math.floor(idx / h);
        const row = idx % h;
        const offset = (row * w + col) * 4;
        data[offset] = 255;
        data[offset + 1] = 255;
        data[offset + 2] = 255;
        data[offset + 3] = 255;
      }
      idx++;
    }
    pixel = 1 - pixel;
  }

  ctx.putImageData(imageData, 0, 0);
  return canvas;
}

/**
 * Compute a tight alpha bounding box directly from uncompressed RLE counts.
 * This avoids full bitmap materialization + getImageData scan on the main thread.
 */
export function rleCountsToBounds(
  counts: number[],
  size: [number, number],
): MaskBounds | null {
  const [h, w] = size;
  if (h <= 0 || w <= 0 || counts.length === 0) return null;

  let minX = w;
  let minY = h;
  let maxX = -1;
  let maxY = -1;

  let idx = 0;
  let pixel = 0; // 0 background, 1 foreground

  for (const run of counts) {
    if (run <= 0) continue;

    if (pixel === 1) {
      const endIdx = idx + run - 1;
      let cursor = idx;
      while (cursor <= endIdx) {
        const col = Math.floor(cursor / h);
        if (col < 0 || col >= w) break;

        const rowStart = cursor % h;
        const remainingInCol = h - rowStart;
        const segLen = Math.min(remainingInCol, endIdx - cursor + 1);
        const rowEnd = rowStart + segLen - 1;

        if (col < minX) minX = col;
        if (col > maxX) maxX = col;
        if (rowStart < minY) minY = rowStart;
        if (rowEnd > maxY) maxY = rowEnd;

        cursor += segLen;
      }
    }

    idx += run;
    pixel = 1 - pixel;
  }

  if (maxX < minX || maxY < minY) return null;

  return {
    x: minX,
    y: minY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}

/**
 * Convert raw mask float data to column-major (Fortran) RLE.
 * Threshold at 0.0 — values > 0 are foreground.
 */
export function maskDataToFortranArrayToRle(
  input: ArrayLike<number>,
  h: number,
  w: number,
): number[] {
  // Flatten row-major input to column-major order
  const total = h * w;
  const colMajor = new Uint8Array(total);
  for (let col = 0; col < w; col++) {
    for (let row = 0; row < h; row++) {
      colMajor[col * h + row] = input[row * w + col] > 0 ? 1 : 0;
    }
  }

  // Run-length encode
  const counts: number[] = [];
  let currentVal = 0;
  let runLen = 0;
  for (let i = 0; i < total; i++) {
    if (colMajor[i] === currentVal) {
      runLen++;
    } else {
      counts.push(runLen);
      runLen = 1;
      currentVal = 1 - currentVal;
    }
  }
  counts.push(runLen);
  return counts;
}

export type MaskBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const MASK_BITMAP_KEYS = [
  "bitmap_data_url",
  "bitmap_url",
  "bitmap_uri",
  "mask_data_url",
  "mask_url",
  "mask_uri",
  "png_data_url",
  "png_url",
  "url",
  "uri",
] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function parseNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function hasImageDataAccess(
  ctx: RenderingContext | OffscreenCanvasRenderingContext2D | null,
): ctx is CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D {
  return ctx !== null && "getImageData" in ctx;
}

function toMaskBounds(input: unknown): MaskBounds | null {
  if (Array.isArray(input) && input.length >= 4) {
    const x = parseNumber(input[0]);
    const y = parseNumber(input[1]);
    const width = parseNumber(input[2]);
    const height = parseNumber(input[3]);
    if (x !== null && y !== null && width !== null && height !== null) {
      return { x, y, width, height };
    }
    return null;
  }

  const obj = asRecord(input);
  const x = parseNumber(obj.x);
  const y = parseNumber(obj.y);
  const width = parseNumber(obj.width);
  const height = parseNumber(obj.height);
  if (x !== null && y !== null && width !== null && height !== null) {
    return { x, y, width, height };
  }
  return null;
}

export function resolveMaskBitmapSource(input: {
  data?: Record<string, unknown>;
  metadata?: unknown;
}): string | null {
  const data = asRecord(input.data);
  const metadata = asRecord(input.metadata ?? data.inference_metadata);

  for (const key of MASK_BITMAP_KEYS) {
    const dataValue = data[key];
    if (typeof dataValue === "string" && dataValue.length > 0) {
      return dataValue;
    }
    const metadataValue = metadata[key];
    if (typeof metadataValue === "string" && metadataValue.length > 0) {
      return metadataValue;
    }
  }

  return null;
}

export function resolveMaskBounds(input: {
  data?: Record<string, unknown>;
  metadata?: unknown;
}): MaskBounds | null {
  const data = asRecord(input.data);
  const metadata = asRecord(input.metadata ?? data.inference_metadata);

  const directBounds =
    toMaskBounds(data.bounds) ??
    toMaskBounds(data.bbox) ??
    toMaskBounds(metadata.bounds) ??
    toMaskBounds(metadata.bbox);
  if (directBounds) return directBounds;

  return null;
}

export function dataUrlToBlob(dataUrl: string): Blob | null {
  const parts = dataUrl.split(",");
  if (parts.length !== 2) return null;

  const match = /^data:([^;]+);base64$/.exec(parts[0]);
  if (!match) return null;

  try {
    const mimeType = match[1] || "image/png";
    const bytes = atob(parts[1]);
    const buffer = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i += 1) {
      buffer[i] = bytes.charCodeAt(i);
    }
    return new Blob([buffer], { type: mimeType });
  } catch {
    return null;
  }
}

export function getAlphaBoundingBox(canvas: HTMLCanvasElement | OffscreenCanvas): MaskBounds | null {
  const ctx = canvas.getContext("2d");
  if (!hasImageDataAccess(ctx)) return null;

  const { width, height } = canvas;
  if (width === 0 || height === 0) return null;

  const imageData = ctx.getImageData(0, 0, width, height).data;

  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const alpha = imageData[(y * width + x) * 4 + 3];
      if (alpha === 0) continue;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }

  if (maxX < minX || maxY < minY) {
    return null;
  }

  return {
    x: minX,
    y: minY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}

/**
 * Convert a canvas alpha channel to column-major (Fortran order) RLE.
 * Pixels with alpha > 0 are foreground (1), transparent pixels are background (0).
 */
export function canvasAlphaToRle(
  canvas: HTMLCanvasElement | OffscreenCanvas,
): { counts: number[]; size: [number, number] } {
  const ctx = (canvas as HTMLCanvasElement).getContext("2d") as
    | CanvasRenderingContext2D
    | OffscreenCanvasRenderingContext2D;
  const { width, height } = canvas;
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  const total = width * height;

  // Convert alpha channel to column-major (Fortran order) binary array
  const colMajor = new Uint8Array(total);
  for (let col = 0; col < width; col++) {
    for (let row = 0; row < height; row++) {
      colMajor[col * height + row] = data[(row * width + col) * 4 + 3] > 0 ? 1 : 0;
    }
  }

  // Run-length encode
  const counts: number[] = [];
  let currentVal = 0;
  let runLen = 0;
  for (let i = 0; i < total; i++) {
    if (colMajor[i] === currentVal) {
      runLen++;
    } else {
      counts.push(runLen);
      runLen = 1;
      currentVal = 1 - currentVal;
    }
  }
  counts.push(runLen);
  return { counts, size: [height, width] };
}

export function hexToRGBA(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
