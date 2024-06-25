/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { writable } from "svelte/store";

// Exports

type VideoControls = {
  zoomLevel: number[];
  intervalId: number;
  isLoaded: boolean;
  videoSpeed: number;
};

export const lastFrameIndex = writable<number>();
export const currentFrameIndex = writable<number>(0);
export const objectIdBeingEdited = writable<string | null>(null);
export const videoControls = writable<VideoControls>({
  zoomLevel: [100],
  intervalId: 0,
  isLoaded: false,
  videoSpeed: 100,
});
