/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type LoadedImagesPerView } from "$lib/types/dataset";

import { reactiveStore } from "./reactiveStore.svelte";

// ─── Playback state ─────────────────────────────────────────────────────────

type PlaybackState = {
  intervalId: number;
  isLoaded: boolean;
  isBuffering: boolean;
  videoSpeed: number;
};

export const playbackState = reactiveStore<PlaybackState>({
  intervalId: 0,
  isLoaded: false,
  isBuffering: false,
  videoSpeed: 100,
});

// ─── Timeline zoom ──────────────────────────────────────────────────────────

export const timelineZoom = reactiveStore<number[]>([100]);

// ─── Frame navigation ───────────────────────────────────────────────────────

export const imagesPerView = reactiveStore<LoadedImagesPerView>({});
export const lastFrameIndex = reactiveStore<number | undefined>(undefined);
export const currentFrameIndex = reactiveStore<number>(0);
export const currentItemId = reactiveStore<string>("");
export const videoViewNames = reactiveStore<string[]>([]);

export function resetVideoStores() {
  playbackState.value = {
    intervalId: 0,
    isLoaded: false,
    isBuffering: false,
    videoSpeed: 100,
  };
  imagesPerView.value = {};
  lastFrameIndex.value = undefined;
  currentFrameIndex.value = 0;
  currentItemId.value = "";
  videoViewNames.value = [];
}
