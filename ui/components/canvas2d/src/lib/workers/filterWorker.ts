/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Web Worker that applies image filters (brightness, contrast, channel adjustment,
 * histogram equalization) off the main thread to keep the UI responsive.
 *
 * Communication protocol:
 *   Main → Worker: { imageData: ImageData, filters: FilterParams }
 *   Worker → Main: { imageData: ImageData }
 *
 * ImageData is transferred (zero-copy) in both directions via Transferable.
 */

export interface FilterParams {
  brightness: number;
  contrast: number;
  redRange: [number, number];
  greenRange: [number, number];
  blueRange: [number, number];
  equalizeHistogram: boolean;
}

export interface FilterWorkerMessage {
  imageData: ImageData;
  filters: FilterParams;
  viewName: string;
}

export interface FilterWorkerResult {
  imageData: ImageData;
  viewName: string;
}

function adjustChannels(data: Uint8ClampedArray, filters: FilterParams): void {
  const [redMin, redMax] = filters.redRange;
  const [greenMin, greenMax] = filters.greenRange;
  const [blueMin, blueMax] = filters.blueRange;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    if (r < redMin || r > redMax || g < greenMin || g > greenMax || b < blueMin || b > blueMax) {
      data[i] = 0;
      data[i + 1] = 0;
      data[i + 2] = 0;
    }
  }
}

function applyBrightness(data: Uint8ClampedArray, brightness: number): void {
  const b = brightness * 255;
  for (let i = 0; i < data.length; i += 4) {
    data[i] = Math.min(255, Math.max(0, data[i] + b));
    data[i + 1] = Math.min(255, Math.max(0, data[i + 1] + b));
    data[i + 2] = Math.min(255, Math.max(0, data[i + 2] + b));
  }
}

function applyContrast(data: Uint8ClampedArray, contrast: number): void {
  const factor = (259 * (contrast + 255)) / (255 * (259 - contrast));
  for (let i = 0; i < data.length; i += 4) {
    data[i] = Math.min(255, Math.max(0, factor * (data[i] - 128) + 128));
    data[i + 1] = Math.min(255, Math.max(0, factor * (data[i + 1] - 128) + 128));
    data[i + 2] = Math.min(255, Math.max(0, factor * (data[i + 2] - 128) + 128));
  }
}

function equalizeHistogram(data: Uint8ClampedArray, nPixels: number): void {
  const histR = new Uint32Array(256);
  const histG = new Uint32Array(256);
  const histB = new Uint32Array(256);

  for (let i = 0; i < data.length; i += 4) {
    histR[data[i]]++;
    histG[data[i + 1]]++;
    histB[data[i + 2]]++;
  }

  const cdfR = new Float64Array(256);
  const cdfG = new Float64Array(256);
  const cdfB = new Float64Array(256);
  cdfR[0] = histR[0];
  cdfG[0] = histG[0];
  cdfB[0] = histB[0];
  for (let i = 1; i < 256; i++) {
    cdfR[i] = cdfR[i - 1] + histR[i];
    cdfG[i] = cdfG[i - 1] + histG[i];
    cdfB[i] = cdfB[i - 1] + histB[i];
  }

  let cdfRMin = 0,
    cdfGMin = 0,
    cdfBMin = 0;
  for (let i = 0; i < 256; i++) {
    if (cdfRMin === 0 && cdfR[i] > 0) cdfRMin = cdfR[i];
    if (cdfGMin === 0 && cdfG[i] > 0) cdfGMin = cdfG[i];
    if (cdfBMin === 0 && cdfB[i] > 0) cdfBMin = cdfB[i];
  }

  for (let i = 0; i < 256; i++) {
    cdfR[i] = ((cdfR[i] - cdfRMin) / (nPixels - cdfRMin)) * 255;
    cdfG[i] = ((cdfG[i] - cdfGMin) / (nPixels - cdfGMin)) * 255;
    cdfB[i] = ((cdfB[i] - cdfBMin) / (nPixels - cdfBMin)) * 255;
  }

  for (let i = 0; i < data.length; i += 4) {
    data[i] = Math.round(cdfR[data[i]]);
    data[i + 1] = Math.round(cdfG[data[i + 1]]);
    data[i + 2] = Math.round(cdfB[data[i + 2]]);
  }
}

self.onmessage = (e: MessageEvent<FilterWorkerMessage>) => {
  const { imageData, filters, viewName } = e.data;
  const { data } = imageData;
  const nPixels = imageData.width * imageData.height;

  // Apply filters in the same order as Konva's pipeline
  applyBrightness(data, filters.brightness);
  applyContrast(data, filters.contrast);
  adjustChannels(data, filters);
  if (filters.equalizeHistogram) {
    equalizeHistogram(data, nPixels);
  }

  const result: FilterWorkerResult = { imageData, viewName };
  (self as unknown as Worker).postMessage(result, [imageData.data.buffer]);
};
