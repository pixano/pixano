/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

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
