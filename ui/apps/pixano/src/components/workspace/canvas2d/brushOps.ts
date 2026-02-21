/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Converts the alpha channel of an offscreen canvas to a column-major binary bitmap,
 * then RLE-encodes it.
 */
export function bitmapToRle(canvas: HTMLCanvasElement): number[] {
  const width = canvas.width;
  const height = canvas.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return [];

  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;

  // Build column-major binary bitmap (Fortran order for COCO compatibility)
  const totalPixels = width * height;
  const bitmap = new Uint8Array(totalPixels);
  for (let col = 0; col < width; col++) {
    for (let row = 0; row < height; row++) {
      const srcIdx = (row * width + col) * 4;
      const dstIdx = col * height + row;
      bitmap[dstIdx] = data[srcIdx + 3] > 0 ? 1 : 0;
    }
  }

  // RLE encode
  const counts: number[] = [];
  let count = 1;
  for (let i = 1; i < totalPixels; i++) {
    if (bitmap[i] === bitmap[i - 1]) {
      count++;
    } else {
      counts.push(count);
      count = 1;
    }
  }
  counts.push(count);

  // RLE must start with a run of zeros. If bitmap[0] is 1, prepend a 0-length run.
  if (bitmap[0] === 1) {
    counts.unshift(0);
  }

  return counts;
}

/**
 * Decode RLE counts into an offscreen canvas.
 * Paints white pixels (with full alpha) where the mask is set.
 */
export function rleToBitmap(
  counts: number[],
  width: number,
  height: number,
  canvas: HTMLCanvasElement,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const imageData = ctx.createImageData(width, height);
  const data = imageData.data;

  // Decode column-major RLE into pixel positions
  let pixel = 0;
  let bit = false; // RLE starts with zeros
  for (const count of counts) {
    for (let j = 0; j < count; j++) {
      if (bit) {
        // Convert column-major index back to row-major
        const col = Math.floor(pixel / height);
        const row = pixel % height;
        const idx = (row * width + col) * 4;
        data[idx] = 255; // R
        data[idx + 1] = 255; // G
        data[idx + 2] = 255; // B
        data[idx + 3] = 255; // A
      }
      pixel++;
    }
    bit = !bit;
  }

  ctx.putImageData(imageData, 0, 0);
}

/**
 * Draw a filled circle on the canvas context.
 */
export function drawBrushCircle(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  mode: "draw" | "erase",
): void {
  ctx.globalCompositeOperation = mode === "draw" ? "source-over" : "destination-out";
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = "white";
  ctx.fill();
}

/**
 * Generate intermediate points between two positions for continuous brush strokes.
 * Uses spacing based on brush radius to avoid gaps.
 */
export function interpolatePoints(
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  spacing: number,
): Array<{ x: number; y: number }> {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const dist = Math.sqrt(dx * dx + dy * dy);

  if (dist < spacing) return [p2];

  const points: Array<{ x: number; y: number }> = [];
  const steps = Math.ceil(dist / spacing);
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    points.push({
      x: p1.x + dx * t,
      y: p1.y + dy * t,
    });
  }
  return points;
}

/**
 * Check if an offscreen canvas has any non-transparent pixels.
 */
export function isMaskEmpty(canvas: HTMLCanvasElement): boolean {
  const ctx = canvas.getContext("2d");
  if (!ctx) return true;

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = imageData.data;

  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 0) return false;
  }
  return true;
}
