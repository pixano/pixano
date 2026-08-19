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
export function rleToBitmapCanvas(counts: number[], size: [number, number]): OffscreenCanvas {
  const [h, w] = size;
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Failed to get 2d context from OffscreenCanvas");
  const imageData = ctx.createImageData(w, h);
  const data = imageData.data;

  let idx = 0;
  let pixel = 0;
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
 * Convert a canvas alpha channel to column-major (Fortran order) RLE.
 * Pixels with alpha > 0 are foreground (1), transparent pixels are background (0).
 */
export function canvasAlphaToRle(canvas: HTMLCanvasElement | OffscreenCanvas): {
  counts: number[];
  size: [number, number];
} {
  const ctx = (canvas as HTMLCanvasElement).getContext("2d") as
    | CanvasRenderingContext2D
    | OffscreenCanvasRenderingContext2D;
  const { width, height } = canvas;
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  const total = width * height;

  const colMajor = new Uint8Array(total);
  for (let col = 0; col < width; col++) {
    for (let row = 0; row < height; row++) {
      colMajor[col * height + row] = data[(row * width + col) * 4 + 3] > 0 ? 1 : 0;
    }
  }

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
