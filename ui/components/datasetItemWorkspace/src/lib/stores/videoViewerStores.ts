/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { writable } from "svelte/store";

import { type HTMLImage, type ImagesPerView } from "@pixano/core";

// Exports

type VideoControls = {
  zoomLevel: number[];
  intervalId: number;
  isLoaded: boolean;
  videoSpeed: number;
};

export const imagesPerView = writable<ImagesPerView>({});
export const imagesPerViewBuffer = writable<Record<string, HTMLImage[]>>({});
export const imagesFilesUrlsByFrame = writable<
  Record<string, { id: string; url: string } | undefined>[]
>([]);

export const lastFrameIndex = writable<number>();
export const currentFrameIndex = writable<number>(0);
export const videoControls = writable<VideoControls>({
  zoomLevel: [100],
  intervalId: 0,
  isLoaded: false,
  videoSpeed: 100,
});
