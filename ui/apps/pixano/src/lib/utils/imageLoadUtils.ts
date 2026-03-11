/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Image as ImageJS } from "image-js";

import { Image, isImage, type LoadedImagesPerView } from "$lib/types/dataset";
import { filters, itemMetas } from "$lib/stores/workspaceStores.svelte";
import { toClientAssetUrl } from "$lib/utils/coreUtils";

export const equalizeHistogram = (imageData: ImageData) => {
  const { width, height, data } = imageData;
  const nPixels = width * height;

  const histR: number[] = new Array(256).fill(0) as number[];
  const histG: number[] = new Array(256).fill(0) as number[];
  const histB: number[] = new Array(256).fill(0) as number[];

  for (let i = 0; i < nPixels * 4; i += 4) {
    histR[data[i]]++;
    histG[data[i + 1]]++;
    histB[data[i + 2]]++;
  }

  const cdfR: number[] = new Array(256).fill(0) as number[];
  const cdfG: number[] = new Array(256).fill(0) as number[];
  const cdfB: number[] = new Array(256).fill(0) as number[];
  cdfR[0] = histR[0];
  cdfG[0] = histG[0];
  cdfB[0] = histB[0];

  for (let i = 1; i < 256; i++) {
    cdfR[i] = cdfR[i - 1] + histR[i];
    cdfG[i] = cdfG[i - 1] + histG[i];
    cdfB[i] = cdfB[i - 1] + histB[i];
  }

  const cdfRMin = cdfR.find((value) => value > 0);
  const cdfGMin = cdfG.find((value) => value > 0);
  const cdfBMin = cdfB.find((value) => value > 0);

  for (let i = 0; i < 256; i++) {
    cdfR[i] = ((cdfR[i] - cdfRMin) / (nPixels - cdfRMin)) * 255;
    cdfG[i] = ((cdfG[i] - cdfGMin) / (nPixels - cdfGMin)) * 255;
    cdfB[i] = ((cdfB[i] - cdfBMin) / (nPixels - cdfBMin)) * 255;
  }

  for (let i = 0; i < nPixels * 4; i += 4) {
    data[i] = Math.round(cdfR[data[i]]);
    data[i + 1] = Math.round(cdfG[data[i + 1]]);
    data[i + 2] = Math.round(cdfB[data[i + 2]]);
  }
};

/**
 * Normalize the pixel values of a 16-bit image to 8-bit range [0, 255].
 * Mutates the image in place.
 */
export const normalize16BitImage = (image: ImageJS, min: number, max: number): void => {
  image.bitDepth = 8;
  image.maxValue = 255;

  const nPixels: number = image.size;
  if (image.channels === 4) {
    for (let i = 0; i < nPixels; i += 4) {
      let rPixel: number = image.data[i];
      let gPixel: number = image.data[i + 1];
      let bPixel: number = image.data[i + 2];

      rPixel = rPixel < min ? 0 : rPixel > max ? 255 : ((rPixel - min) / (max - min)) * 255;
      gPixel = gPixel < min ? 0 : gPixel > max ? 255 : ((gPixel - min) / (max - min)) * 255;
      bPixel = bPixel < min ? 0 : bPixel > max ? 255 : ((bPixel - min) / (max - min)) * 255;

      image.data[i] = rPixel;
      image.data[i + 1] = gPixel;
      image.data[i + 2] = bPixel;
    }
  } else {
    for (let i = 0; i < nPixels; ++i) {
      let pixel: number = image.data[i];
      pixel = pixel < min ? 0 : pixel > max ? 255 : ((pixel - min) / (max - min)) * 255;
      image.data[i] = pixel;
    }
  }
};

async function imageToBitmap(img: ImageJS): Promise<ImageBitmap> {
  const offscreen = new OffscreenCanvas(img.width, img.height);
  const ctx = offscreen.getContext("2d");
  if (!ctx) throw new Error("Failed to get 2d context");
  ctx.putImageData(
    new ImageData(new Uint8ClampedArray(img.getRGBAData()), img.width, img.height),
    0,
    0,
  );
  return createImageBitmap(offscreen);
}

export interface LoadImagesOptions {
  /** If true, sort result keys for deterministic ordering. */
  sortKeys?: boolean;
  /** If true, unwrap arrays (take first element). */
  unwrapArrays?: boolean;
  /** If true, filter views to only images (isImage check). */
  filterImages?: boolean;
}

/**
 * Load images from views, probing bit depth and normalizing 16-bit images.
 */
export async function loadImagesFromViews(
  views: Record<string, Image | Image[]>,
  options: LoadImagesOptions = {},
): Promise<LoadedImagesPerView> {
  const {
    sortKeys = false,
    unwrapArrays = false,
    filterImages = false,
  } = options;

  const images: LoadedImagesPerView = {};
  const promises: Promise<void>[] = Object.entries(views).map(async ([key, value]) => {
    const imageObject = unwrapArrays && Array.isArray(value) ? value[0] : value;
    if (Array.isArray(imageObject)) return;
    if (filterImages && !isImage(imageObject)) return;
    if (!isImage(imageObject)) return;
    if (!imageObject.data.url) return;

    const imageUrl = toClientAssetUrl(imageObject.data.url);
    const img: ImageJS = await ImageJS.load(imageUrl);
    const bitDepth = img.bitDepth as number;
    const format = bitDepth === 1 ? "1bit" : bitDepth === 8 ? "8bit" : "16bit";
    const color = img.channels === 4 ? "rgba" : img.channels === 3 ? "rgb" : "grayscale";
    itemMetas.update((metas) => (metas ? { ...metas, format, color } : metas));

    if (format === "16bit") {
      normalize16BitImage(img, filters.value.u16BitRange[0], filters.value.u16BitRange[1]);
    }
    const bitmap = await imageToBitmap(img);
    images[key] = [{ id: imageObject.id, element: bitmap }];
  });

  await Promise.all(promises);

  if (sortKeys) {
    const sorted: LoadedImagesPerView = {};
    for (const key of Object.keys(images).sort()) {
      sorted[key] = images[key];
    }
    return sorted;
  }

  return images;
}
