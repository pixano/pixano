/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type LoadedImage, type LoadedImagesPerView } from "$lib/types/dataset";

import { reactiveStore } from "./reactiveStore.svelte";

type VideoControls = {
  zoomLevel: number[];
  intervalId: number;
  isLoaded: boolean;
  videoSpeed: number;
};

export const imagesPerView = reactiveStore<LoadedImagesPerView>({});
export const imagesPerViewBuffer = reactiveStore<Record<string, LoadedImage[]>>({});
export const lastFrameIndex = reactiveStore<number | undefined>(undefined);
export const currentFrameIndex = reactiveStore<number>(0);
export const currentItemId = reactiveStore<string>("");
export const videoViewNames = reactiveStore<string[]>([]);
export const videoControls = reactiveStore<VideoControls>({
  zoomLevel: [100],
  intervalId: 0,
  isLoaded: false,
  videoSpeed: 100,
});
