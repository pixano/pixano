/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Image as ImageJS } from "image-js";

import { Image, isImage, type LoadedImagesPerView } from "$lib/types/dataset";
import { filters, itemMetas } from "$lib/stores/workspaceStores.svelte";

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

export interface LoadImagesOptions {
  /** If true, use native URL for 8-bit images instead of toDataURL roundtrip. */
  useNativeUrl?: boolean;
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
    useNativeUrl = false,
    sortKeys = false,
    unwrapArrays = false,
    filterImages = false,
  } = options;

  const images: LoadedImagesPerView = {};
  const promises: Promise<void>[] = Object.entries(views).map(async ([key, value]) => {
    const imageObject = unwrapArrays && Array.isArray(value) ? value[0] : value;
    if (Array.isArray(imageObject)) return;
    if (filterImages && !isImage(imageObject)) return;

    const img: ImageJS = await ImageJS.load(`/${imageObject.data.url}`);
    const bitDepth = img.bitDepth as number;
    const format = bitDepth === 1 ? "1bit" : bitDepth === 8 ? "8bit" : "16bit";
    const color = img.channels === 4 ? "rgba" : img.channels === 3 ? "rgb" : "grayscale";
    itemMetas.update((metas) => (metas ? { ...metas, format, color } : metas));

    if (format === "16bit") {
      normalize16BitImage(img, filters.value.u16BitRange[0], filters.value.u16BitRange[1]);
      const image: HTMLImageElement = document.createElement("img");
      image.src = img.toDataURL();
      images[key] = [{ id: imageObject.id, element: image }];
    } else if (useNativeUrl) {
      const image: HTMLImageElement = document.createElement("img");
      image.src = `/${imageObject.data.url}`;
      images[key] = [{ id: imageObject.id, element: image }];
    } else {
      const image: HTMLImageElement = document.createElement("img");
      image.src = img.toDataURL();
      images[key] = [{ id: imageObject.id, element: image }];
    }
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
