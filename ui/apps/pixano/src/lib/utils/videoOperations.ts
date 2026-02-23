/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { Track, type Annotation } from "$lib/types/dataset";
import { sourcesStore } from "$lib/stores/appStores.svelte";

import {
  imagesFilesUrlsByFrame,
  imagesPerView,
  imagesPerViewBuffer,
  lastFrameIndex,
} from "$lib/stores/videoStores.svelte";
import { saveTo } from "$lib/utils/saveItemUtils";
import { getPixanoSource } from "$lib/utils/entityLookupUtils";
import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";

let timerId: ReturnType<typeof setTimeout>;
// buffer
const ratioOfBackwardBuffer = 0.1;
const bufferSize = 200;
let previousCount: number = 0;
let nextCount: number = 0;

export const splitTrackInTwo = (
  track2split: Track,
  prev: number,
  next: number,
): Annotation => {
  const rightTrackOrig = structuredClone(track2split);
  const { ui, ...noUIfieldsTrack } = rightTrackOrig;
  const rightTrack = new Track(noUIfieldsTrack);
  rightTrack.id = nanoid(10);
  rightTrack.data.start_timestep = next;
  rightTrack.ui = ui;
  //note: get object links from original object, as structuredClone lose class specifics
  rightTrack.ui.childs = track2split.ui.childs.filter((ann) => ann.ui.frame_index! >= next);
  rightTrack.ui.top_entities = track2split.ui.top_entities;
  //track2split become left track
  track2split.data.end_timestep = prev;
  track2split.ui.childs = track2split.ui.childs.filter((ann) => ann.ui.frame_index! <= prev);

  const pixSource = getPixanoSource(sourcesStore);
  track2split.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
  saveTo("update", track2split);
  rightTrack.data.source_ref = { id: pixSource.id, name: pixSource.table_info.name };
  saveTo("add", rightTrack);
  return rightTrack;
};

export const setBufferSpecs = () => {
  const n_view = Object.keys(imagesPerViewBuffer.value).length;
  previousCount = Math.round((ratioOfBackwardBuffer * bufferSize) / n_view);
  nextCount = Math.round(((1 - ratioOfBackwardBuffer) * bufferSize) / n_view);
  //reset imagesPerView store
  imagesPerView.value = {};
};

function preloadViewsImage(index: number) {
  Object.entries(imagesFilesUrlsByFrame.value[index]).map(([viewKey, im_ref]) => {
    if (im_ref && !imagesPerViewBuffer.value[viewKey][index]) {
      void new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.src = `/${im_ref.url}`;
        img.onload = () => {
          imagesPerViewBuffer.update((buff) => {
            buff[viewKey][index] = {
              id: im_ref.id,
              element: img,
            };
            return buff;
          });
          resolve();
        };
        img.onerror = () => {
          console.warn(`Failed to load image: ${im_ref.url}`);
          reject(new Error(`Failed to load image: ${im_ref.url}`));
        };
      });
    }
  });
}

function preloadImagesProgressively(currentIndex: number = 0) {
  const previous: number[] = [];
  const next: number[] = [];

  const num_frames = lastFrameIndex.value + 1;
  if (num_frames > 1) {
    // previous (inverted and circular)
    for (let i = 1; i <= previousCount; i++) {
      previous.push((currentIndex - i + num_frames) % num_frames);
    }
    // next (inculing current, circular)
    for (let i = 0; i < nextCount; i++) {
      next.push((currentIndex + i) % num_frames);
    }
  }
  const includedIndices = new Set([...previous, ...next]);
  const excludedIndices = Array.from({ length: num_frames }, (_, i) => i).filter(
    (index) => !includedIndices.has(index),
  );

  clearTimeout(timerId); // reinit timer on each update
  timerId = setTimeout(() => {
    for (const i of next) {
      preloadViewsImage(i);
    }
    for (const i of previous) {
      preloadViewsImage(i);
    }
  }, 20); // timeout to spare bandwith (cancel outdated updates)

  //delete buffered images out of currentIndex window (currentIndex -10 : currentIndex + 30)
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
}

export const updateView = (imageIndex: number) => {
  if (imagesFilesUrlsByFrame.value.length === 0) return;
  preloadImagesProgressively(imageIndex);
  const buffer = imagesPerViewBuffer.value;
  Object.entries(imagesFilesUrlsByFrame.value[imageIndex]).forEach(([key, im_ref]) => {
    if (key in buffer && buffer[key][imageIndex] && buffer[key][imageIndex].element.complete) {
      imagesPerView.update((ipv) => {
        ipv[key] = [...(ipv[key] || []), buffer[key][imageIndex]].slice(-2);
        return ipv;
      });
    } else {
      if (im_ref) {
        const image = new Image();
        const src = `/${im_ref.url}`;
        if (!src) return;
        image.src = src;
        //NOTE double image, avoid flashing by "swapping" with previous image
        imagesPerView.update((ipv) => {
          ipv[key] = [...(ipv[key] || []), { id: im_ref.id, element: image }].slice(-2);
          return ipv;
        });
      } else {
        //console.warn("Media not present")
      }
    }
  });
  loadViewEmbeddings(true);
};
