/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { Track, type Annotation } from "$lib/types/dataset";
import { currentDatasetStore, sourcesStore } from "$lib/stores/appStores.svelte";

import {
  currentItemId,
  imagesPerView,
  imagesPerViewBuffer,
  lastFrameIndex,
  videoViewNames,
} from "$lib/stores/videoStores.svelte";
import { saveTo } from "$lib/utils/saveItemUtils";
import { getPixanoSource } from "$lib/utils/entityLookupUtils";
import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";
import * as api from "$lib/api";

let timerId: ReturnType<typeof setTimeout>;
// buffer
const ratioOfBackwardBuffer = 0.1;
const bufferSize = 200;
let previousCount: number = 0;
let nextCount: number = 0;

// Track which batch ranges are already fetched or in-flight per view
const fetchedRanges: Map<string, Set<string>> = new Map();

function batchKey(startFrame: number, batchSize: number): string {
  return `${startFrame}-${batchSize}`;
}

export const splitTrackInTwo = (
  track2split: Track,
  prev: number,
  next: number,
): Annotation => {
  const rightTrackOrig = structuredClone(track2split);
  const { ui, ...noUIfieldsTrack } = rightTrackOrig;
  const rightTrack = new Track(noUIfieldsTrack);
  rightTrack.id = nanoid(10);
  rightTrack.data.start_frame = next;
  rightTrack.ui = ui;
  //note: get object links from original object, as structuredClone lose class specifics
  rightTrack.ui.childs = track2split.ui.childs.filter((ann) => ann.ui.frame_index >= next);
  rightTrack.ui.top_entities = track2split.ui.top_entities;
  //track2split become left track
  track2split.data.end_frame = prev;
  track2split.ui.childs = track2split.ui.childs.filter((ann) => ann.ui.frame_index <= prev);

  const pixSource = getPixanoSource(sourcesStore);
  track2split.data.source_id = pixSource.id;
  saveTo("update", track2split);
  rightTrack.data.source_id = pixSource.id;
  saveTo("add", rightTrack);
  return rightTrack;
};

export const setBufferSpecs = () => {
  const n_view = Object.keys(imagesPerViewBuffer.value).length;
  previousCount = Math.round((ratioOfBackwardBuffer * bufferSize) / n_view);
  nextCount = Math.round(((1 - ratioOfBackwardBuffer) * bufferSize) / n_view);
  //reset imagesPerView store
  imagesPerView.value = {};
  // Reset fetch tracking
  fetchedRanges.clear();
};

/**
 * Convert a Blob to an HTMLImageElement via object URL.
 */
function blobToImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to decode frame blob"));
    };
    img.src = url;
  });
}

/**
 * Fetch a batch of frames for a single view and store them in the buffer.
 */
async function preloadBatch(
  viewName: string,
  datasetId: string,
  itemId: string,
  startFrame: number,
  batchSize: number,
): Promise<void> {
  const key = batchKey(startFrame, batchSize);

  // Initialize view tracking set if needed
  let viewRanges = fetchedRanges.get(viewName);
  if (!viewRanges) {
    viewRanges = new Set();
    fetchedRanges.set(viewName, viewRanges);
  }

  // Skip if already fetched or in-flight
  if (viewRanges.has(key)) return;
  viewRanges.add(key);

  const frames = await api.getViewFrameBatch(datasetId, viewName, itemId, startFrame, batchSize);

  for (const [frameIndex, blob] of frames) {
    // Skip if already in buffer
    if (imagesPerViewBuffer.value[viewName]?.[frameIndex]) continue;

    try {
      const img = await blobToImage(blob);
      imagesPerViewBuffer.update((buff) => {
        if (!buff[viewName]) buff[viewName] = [];
        buff[viewName][frameIndex] = {
          id: `${viewName}_${frameIndex}`,
          element: img,
        };
        return buff;
      });
    } catch (e) {
      console.warn(`Failed to decode frame ${frameIndex} for view ${viewName}:`, e);
    }
  }
}

function preloadImagesProgressively(currentIndex: number = 0) {
  const numFrames = (lastFrameIndex.value ?? -1) + 1;
  if (numFrames <= 1) return;

  const datasetId = currentDatasetStore.value?.id;
  const itemId = currentItemId.value;
  const viewNames = videoViewNames.value;
  if (!datasetId || !itemId || viewNames.length === 0) return;

  const previous: number[] = [];
  const next: number[] = [];

  // previous (inverted and circular)
  for (let i = 1; i <= previousCount; i++) {
    previous.push((currentIndex - i + numFrames) % numFrames);
  }
  // next (including current, circular)
  for (let i = 0; i < nextCount; i++) {
    next.push((currentIndex + i) % numFrames);
  }

  const includedIndices = new Set([...previous, ...next]);
  const excludedIndices = Array.from({ length: numFrames }, (_, i) => i).filter(
    (index) => !includedIndices.has(index),
  );

  clearTimeout(timerId);
  timerId = setTimeout(() => {
    // Compute the range to fetch as a single batch per view
    const allIndices = [...next, ...previous];
    if (allIndices.length === 0) return;
    const minFrame = Math.min(...allIndices);
    const maxFrame = Math.max(...allIndices);
    const batchSize = maxFrame - minFrame + 1;

    for (const viewName of viewNames) {
      void preloadBatch(viewName, datasetId, itemId, minFrame, batchSize);
    }
  }, 20);

  //delete buffered images out of currentIndex window
  imagesPerViewBuffer.update((buff) => {
    Object.keys(buff).forEach((viewKey) => {
      for (const i of excludedIndices) {
        if (i in buff[viewKey]) {
          delete buff[viewKey][i]; // eslint-disable-line @typescript-eslint/no-array-delete
        }
      }
    });
    return buff;
  });

  // Clear fetch tracking for evicted ranges so they can be re-fetched if needed
  for (const viewName of viewNames) {
    const viewRanges = fetchedRanges.get(viewName);
    if (viewRanges) {
      // Remove ranges that no longer overlap with the current window
      for (const key of viewRanges) {
        const [start, size] = key.split("-").map(Number);
        const end = start + size;
        // If the entire fetched range is outside the included window, drop it
        const hasOverlap = Array.from(includedIndices).some((idx) => idx >= start && idx < end);
        if (!hasOverlap) {
          viewRanges.delete(key);
        }
      }
    }
  }
}

/**
 * Populate imagesPerView from the buffer for a given frame index.
 * Used by both loadInitialFrames() and updateView().
 */
function populateImagesPerView(imageIndex: number): void {
  const buffer = imagesPerViewBuffer.value;
  for (const viewName of videoViewNames.value) {
    const loaded = buffer[viewName]?.[imageIndex];
    if (loaded?.element?.complete) {
      imagesPerView.update((ipv) => {
        ipv[viewName] = [...(ipv[viewName] || []), loaded].slice(-2);
        return ipv;
      });
    }
  }
}

/**
 * Async entry point for initial frame loading. Fetches the first batch for all views
 * and populates imagesPerView with frame 0. Must resolve before Canvas2D mounts.
 */
export async function loadInitialFrames(): Promise<void> {
  const datasetId = currentDatasetStore.value?.id;
  const itemId = currentItemId.value;
  const viewNames = videoViewNames.value;
  if (!datasetId || !itemId || viewNames.length === 0) return;

  const batchSize = Math.min(
    Math.ceil(bufferSize / viewNames.length),
    (lastFrameIndex.value ?? 0) + 1,
  );
  await Promise.all(
    viewNames.map((vn) => preloadBatch(vn, datasetId, itemId, 0, batchSize)),
  );

  populateImagesPerView(0);
}

export const updateView = (imageIndex: number) => {
  if (lastFrameIndex.value === undefined) return;
  preloadImagesProgressively(imageIndex);
  populateImagesPerView(imageIndex);

  // For cache misses, start a background fetch and update when ready
  const buffer = imagesPerViewBuffer.value;
  for (const viewName of videoViewNames.value) {
    if (!buffer[viewName]?.[imageIndex]?.element?.complete) {
      const datasetId = currentDatasetStore.value?.id;
      const itemId = currentItemId.value;
      if (datasetId && itemId) {
        void preloadBatch(viewName, datasetId, itemId, imageIndex, 1).then(() => {
          populateImagesPerView(imageIndex);
        });
      }
    }
  }
  loadViewEmbeddings(true);
};
