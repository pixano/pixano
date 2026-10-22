/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import { type LoadedImagesPerView } from "$lib/types/dataset";
import { nextTimelineZoom, TIMELINE_ZOOM_MIN, timelineZoomMax } from "$lib/utils/timelineZoom";

// ─── Playback state ─────────────────────────────────────────────────────────

/** Milliseconds per frame when a record's frame rate is unknown (10 fps). */
export const DEFAULT_VIDEO_SPEED_MS = 100;

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
  videoSpeed: DEFAULT_VIDEO_SPEED_MS,
  loop: false,
});

/** The record's frame rate, read from its frame timestamps; null when unknown. */
export const videoFps = reactiveStore<number | null>(null);

/** The frame rate times and the ruler are computed with: the playback rate when unknown. */
export const timelineFps = reactiveDerived<number>(
  () => videoFps.value ?? 1000 / Math.max(playbackState.value.videoSpeed, 1),
);

// ─── Timeline zoom ──────────────────────────────────────────────────────────

export const timelineZoom = reactiveStore<number[]>([100]);

// ─── Frame navigation ───────────────────────────────────────────────────────

export const imagesPerView = reactiveStore<LoadedImagesPerView>({});
export const lastFrameIndex = reactiveStore<number | undefined>(undefined);
export const currentFrameIndex = reactiveStore<number>(0);
export const currentItemId = reactiveStore<string>("");
export const videoViewNames = reactiveStore<string[]>([]);

/** Zoom the timeline one step in (`1`) or out (`-1`), within the slider's range. */
export function stepTimelineZoom(direction: 1 | -1): void {
  const current = timelineZoom.value[0] ?? TIMELINE_ZOOM_MIN;
  const max = timelineZoomMax(lastFrameIndex.value);
  timelineZoom.value = [nextTimelineZoom(current, direction, max)];
}

export function resetVideoStores() {
  playbackState.value = {
    intervalId: 0,
    isLoaded: false,
    isBuffering: false,
    videoSpeed: DEFAULT_VIDEO_SPEED_MS,
    loop: false,
  };
  videoFps.value = null;
  imagesPerView.value = {};
  lastFrameIndex.value = undefined;
  currentFrameIndex.value = 0;
  currentItemId.value = "";
  videoViewNames.value = [];
}
