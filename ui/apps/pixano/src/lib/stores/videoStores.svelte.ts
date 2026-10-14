/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveStore } from "./reactiveStore.svelte";
import { type LoadedImagesPerView } from "$lib/types/dataset";

// ─── Playback state ─────────────────────────────────────────────────────────

type PlaybackState = {
  intervalId: number;
  isLoaded: boolean;
  isBuffering: boolean;
  videoSpeed: number;
  loop: boolean;
};

export const playbackState = reactiveStore<PlaybackState>({
  intervalId: 0,
  isLoaded: false,
  isBuffering: false,
  videoSpeed: 100,
  loop: false,
});

// ─── Timeline zoom ──────────────────────────────────────────────────────────

export const timelineZoom = reactiveStore<number[]>([100]);

// ─── Track timelines visibility ─────────────────────────────────────────────

// Whether the per-track timelines below the main timeline are shown.
export const showTrackTimelines = reactiveStore<boolean>(true);

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
    loop: false,
  };
  imagesPerView.value = {};
  lastFrameIndex.value = undefined;
  currentFrameIndex.value = 0;
  currentItemId.value = "";
  videoViewNames.value = [];
}
