/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { LRUCache } from "$lib/services/LRUCache";
import { currentDatasetStore, sourcesStore } from "$lib/stores/appStores.svelte";
import {
  currentFrameIndex,
  currentItemId,
  imagesPerView,
  lastFrameIndex,
  videoViewNames,
} from "$lib/stores/videoStores.svelte";
import { Tracklet, type Annotation, type LoadedImage } from "$lib/types/dataset";
import { getPixanoSource } from "$lib/utils/entityLookupUtils";
import { saveTo } from "$lib/utils/saveItemUtils";

const NETWORK_BATCH_SIZE = 128;
const PREFETCH_CHUNKS_AHEAD = 2;
const PREFETCH_CHUNKS_BEHIND = 1;
const WARM_DECODE_AHEAD = 8;
const WARM_DECODE_BEHIND = 2;
const PLAYBACK_PREFETCH_TRIGGER = Math.floor(NETWORK_BATCH_SIZE * 0.25);
const PLAYBACK_EXTRA_PREFETCH_CHUNKS = 3;
const BASE_MEMORY_CACHE_SIZE = 96;

type ViewRuntime = {
  availableFrames: Set<number>;
  persistedFrames: Set<number>;
  frameMimeTypes: Map<number, string>;
  inflightChunks: Map<number, Promise<void>>;
  completedChunks: Set<number>;
};

type FrameWaiter = (available: boolean) => void;

type FrameWorkerRequestPayload =
  | {
      type: "initSession";
      datasetId: string;
      itemId: string;
      sessionToken: number;
    }
  | {
      type: "fetchChunk";
      viewName: string;
      startFrame: number;
      batchSize: number;
    }
  | {
      type: "decodeFrame";
      viewName: string;
      frameIndex: number;
      mimeType?: string;
    }
  | { type: "clearSession" };
type FrameWorkerRequest = FrameWorkerRequestPayload & { requestId: number };

type ChunkFrameResult = {
  frameIndex: number;
  mimeType: string;
  persisted: boolean;
};

type FrameWorkerResponse =
  | { requestId: number; ok: true; type: "initSession" }
  | { requestId: number; ok: true; type: "clearSession" }
  | { requestId: number; ok: true; type: "fetchChunk"; frames: ChunkFrameResult[] }
  | { requestId: number; ok: true; type: "decodeFrame"; missing: true }
  | { requestId: number; ok: true; type: "decodeFrame"; missing: false; bitmap: ImageBitmap }
  | { requestId: number; ok: false; type: FrameWorkerRequestPayload["type"]; error: string };
type FrameWorkerSuccessResponse = Extract<FrameWorkerResponse, { ok: true }>;

type WorkerPendingRequest = {
  resolve: (value: FrameWorkerSuccessResponse) => void;
  reject: (error: Error) => void;
};

const viewRuntimes = new Map<string, ViewRuntime>();
const frameWaiters = new Map<string, Set<FrameWaiter>>();
const decodeInflight = new Map<string, Promise<LoadedImage | undefined>>();
const backgroundDownloads = new Map<string, Promise<void>>();

let frameWorker: Worker | null = null;
let workerRequestCounter = 0;
const workerPendingRequests = new Map<number, WorkerPendingRequest>();

function releaseLoadedImage(image: LoadedImage): void {
  if (typeof ImageBitmap !== "undefined" && image.element instanceof ImageBitmap) {
    image.element.close();
  }
}

function releaseImagesPerViewState(): void {
  for (const images of Object.values(imagesPerView.value)) {
    for (const image of images) {
      releaseLoadedImage(image);
    }
  }
}

let decodedFrameCache = new LRUCache<string, LoadedImage>(BASE_MEMORY_CACHE_SIZE, (_key, value) => {
  releaseLoadedImage(value);
});
let sessionVersion = 0;
let activeSessionKey = "";

function rejectPendingWorkerRequests(error: Error): void {
  for (const pending of workerPendingRequests.values()) {
    pending.reject(error);
  }
  workerPendingRequests.clear();
}

function closeFrameWorker(): void {
  if (frameWorker) {
    frameWorker.terminate();
    frameWorker = null;
  }
}

function ensureFrameWorker(): Worker | null {
  if (typeof Worker === "undefined") {
    return null;
  }
  if (frameWorker) {
    return frameWorker;
  }

  frameWorker = new Worker(new URL("../workers/videoFrameWorker.ts", import.meta.url), {
    type: "module",
  });

  frameWorker.onmessage = (event: MessageEvent<FrameWorkerResponse>) => {
    const response = event.data;
    if (!response || typeof response.requestId !== "number") return;
    const pending = workerPendingRequests.get(response.requestId);
    if (!pending) return;

    workerPendingRequests.delete(response.requestId);
    if (!response.ok) {
      pending.reject(new Error("error" in response ? response.error : "Unknown worker error."));
      return;
    }
    pending.resolve(response);
  };

  frameWorker.onerror = (event: ErrorEvent) => {
    const message =
      event.message || "Video frame worker failed while processing frame streaming.";
    rejectPendingWorkerRequests(new Error(message));
    closeFrameWorker();
  };

  return frameWorker;
}

function requestWorker(
  payload: FrameWorkerRequestPayload,
): Promise<FrameWorkerSuccessResponse> {
  const worker = ensureFrameWorker();
  if (!worker) {
    return Promise.reject(new Error("Web Worker is not supported in this browser."));
  }

  const requestId = ++workerRequestCounter;
  const message = { ...payload, requestId } as FrameWorkerRequest;

  return new Promise<FrameWorkerSuccessResponse>((resolve, reject) => {
    workerPendingRequests.set(requestId, { resolve, reject });
    try {
      worker.postMessage(message);
    } catch (error) {
      workerPendingRequests.delete(requestId);
      reject(error instanceof Error ? error : new Error(String(error)));
    }
  });
}

function frameKey(viewName: string, frameIndex: number): string {
  return `${viewName}:${frameIndex}`;
}

function getTotalFrames(): number {
  return (lastFrameIndex.value ?? -1) + 1;
}

function getOrCreateRuntime(viewName: string): ViewRuntime {
  const existing = viewRuntimes.get(viewName);
  if (existing) return existing;

  const created: ViewRuntime = {
    availableFrames: new Set<number>(),
    persistedFrames: new Set<number>(),
    frameMimeTypes: new Map<number, string>(),
    inflightChunks: new Map<number, Promise<void>>(),
    completedChunks: new Set<number>(),
  };
  viewRuntimes.set(viewName, created);
  return created;
}

function resolveFrameWaiters(viewName: string, frameIndex: number, available: boolean): void {
  const waiters = frameWaiters.get(frameKey(viewName, frameIndex));
  if (!waiters) return;
  for (const resolve of waiters) {
    resolve(available);
  }
  frameWaiters.delete(frameKey(viewName, frameIndex));
}

function resolveAllWaiters(available: boolean): void {
  for (const waiters of frameWaiters.values()) {
    for (const resolve of waiters) {
      resolve(available);
    }
  }
  frameWaiters.clear();
}

function waitForFrameAvailable(viewName: string, frameIndex: number): Promise<boolean> {
  const runtime = getOrCreateRuntime(viewName);
  if (runtime.availableFrames.has(frameIndex)) {
    return Promise.resolve(true);
  }

  const key = frameKey(viewName, frameIndex);
  return new Promise<boolean>((resolve) => {
    const waiters = frameWaiters.get(key);
    if (waiters) {
      waiters.add(resolve);
      return;
    }
    frameWaiters.set(key, new Set<FrameWaiter>([resolve]));
  });
}

function chunkForFrame(frameIndex: number): number {
  return Math.floor(frameIndex / NETWORK_BATCH_SIZE);
}

function getChunkRange(chunkIndex: number): { startFrame: number; batchSize: number } | undefined {
  const totalFrames = getTotalFrames();
  if (totalFrames <= 0) return undefined;
  const startFrame = chunkIndex * NETWORK_BATCH_SIZE;
  if (startFrame >= totalFrames || chunkIndex < 0) return undefined;
  return {
    startFrame,
    batchSize: Math.min(NETWORK_BATCH_SIZE, totalFrames - startFrame),
  };
}

function getSessionIdentifiers(): { datasetId: string; itemId: string } | undefined {
  const datasetId = currentDatasetStore.value?.id;
  const itemId = currentItemId.value;
  if (!datasetId || !itemId) return undefined;
  return { datasetId, itemId };
}

function shouldWarmDecode(frameIndex: number): boolean {
  const current = currentFrameIndex.value;
  return (
    frameIndex >= Math.max(0, current - WARM_DECODE_BEHIND) &&
    frameIndex <= current + WARM_DECODE_AHEAD
  );
}

function clampFrameIndex(frameIndex: number): number {
  const max = lastFrameIndex.value ?? 0;
  return Math.max(0, Math.min(frameIndex, max));
}

function isFrameAvailableInAllViews(frameIndex: number): boolean {
  const target = clampFrameIndex(frameIndex);
  const viewNames = videoViewNames.value;
  if (viewNames.length === 0) return false;

  for (const viewName of viewNames) {
    const runtime = getOrCreateRuntime(viewName);
    if (!runtime.availableFrames.has(target)) {
      return false;
    }
  }
  return true;
}

export function isFrameReady(frameIndex: number): boolean {
  if (lastFrameIndex.value === undefined) return false;

  const target = clampFrameIndex(frameIndex);
  const viewNames = videoViewNames.value;
  if (viewNames.length === 0) return false;

  for (const viewName of viewNames) {
    const key = frameKey(viewName, target);
    if (decodedFrameCache.has(key)) continue;

    const runtime = getOrCreateRuntime(viewName);
    if (!runtime.availableFrames.has(target)) {
      return false;
    }
  }

  return true;
}

export function getReadyAheadFrames(frameIndex: number, maxFrames: number): number {
  if (lastFrameIndex.value === undefined || maxFrames <= 0) return 0;

  const anchor = clampFrameIndex(frameIndex);
  const remaining = Math.max(0, (lastFrameIndex.value ?? anchor) - anchor);
  const limit = Math.min(maxFrames, remaining);

  let ready = 0;
  for (let offset = 1; offset <= limit; offset++) {
    if (!isFrameAvailableInAllViews(anchor + offset)) {
      break;
    }
    ready = offset;
  }

  return ready;
}

export async function ensureFrameAvailable(imageIndex: number): Promise<boolean> {
  if (lastFrameIndex.value === undefined) return false;

  const target = clampFrameIndex(imageIndex);
  const loaded = await Promise.all(
    videoViewNames.value.map((viewName) => ensureFrameReady(viewName, target)),
  );

  preloadAround(target);
  return loaded.every((value) => value !== undefined);
}

export function primePlaybackPrefetch(frameIndex: number): void {
  if (lastFrameIndex.value === undefined) return;

  const anchor = clampFrameIndex(frameIndex);
  preloadAround(anchor);

  if (anchor % NETWORK_BATCH_SIZE < PLAYBACK_PREFETCH_TRIGGER) {
    return;
  }

  const nextChunk = chunkForFrame(anchor) + 1;
  for (const viewName of videoViewNames.value) {
    for (let step = 0; step < PLAYBACK_EXTRA_PREFETCH_CHUNKS; step++) {
      void requestChunk(viewName, nextChunk + step);
    }
  }
}

export async function waitForReadyAheadFrames(
  frameIndex: number,
  requiredAheadFrames: number,
): Promise<boolean> {
  if (lastFrameIndex.value === undefined || requiredAheadFrames <= 0) return true;

  const anchor = clampFrameIndex(frameIndex);
  const maxAhead = Math.max(0, (lastFrameIndex.value ?? anchor) - anchor);
  const targetAhead = Math.min(requiredAheadFrames, maxAhead);
  if (targetAhead <= 0) return true;

  const targetFrame = anchor + targetAhead;
  primePlaybackPrefetch(anchor);

  const startChunk = chunkForFrame(anchor);
  const targetChunk = chunkForFrame(targetFrame);
  const ready = await Promise.all(
    videoViewNames.value.map(async (viewName) => {
      for (let chunk = startChunk; chunk <= targetChunk; chunk++) {
        void requestChunk(viewName, chunk);
      }
      const runtime = getOrCreateRuntime(viewName);
      if (runtime.availableFrames.has(targetFrame)) return true;
      return waitForFrameAvailable(viewName, targetFrame);
    }),
  );

  return ready.every(Boolean);
}

/**
 * Read + decode one frame into the small in-memory LRU render cache.
 *
 * Memory policy:
 * - OPFS is the source of truth for long videos.
 * - LRU holds only recently rendered/adjacent frames to keep UI snappy.
 */
async function decodeAndCacheFrame(viewName: string, frameIndex: number): Promise<LoadedImage | undefined> {
  const key = frameKey(viewName, frameIndex);
  const inMemory = decodedFrameCache.get(key);
  if (inMemory) return inMemory;

  const inflight = decodeInflight.get(key);
  if (inflight !== undefined) return inflight;

  const decodePromise = (async () => {
    const runtime = getOrCreateRuntime(viewName);
    const decodeResponse = await requestWorker({
      type: "decodeFrame",
      viewName,
      frameIndex,
      mimeType: runtime.frameMimeTypes.get(frameIndex),
    });
    if (decodeResponse.type !== "decodeFrame") {
      return undefined;
    }
    if (decodeResponse.missing !== false) {
      return undefined;
    }

    const image = decodeResponse.bitmap;

    const loaded: LoadedImage = {
      id: `${viewName}_${frameIndex}`,
      element: image,
    };

    decodedFrameCache.set(key, loaded);
    return loaded;
  })().finally(() => {
    decodeInflight.delete(key);
  });

  decodeInflight.set(key, decodePromise);
  return decodePromise;
}

function pushImageToCanvasView(viewName: string, loaded: LoadedImage): void {
  imagesPerView.update((state) => {
    const previous = state[viewName] ?? [];
    if (previous[previous.length - 1]?.id === loaded.id) {
      return state;
    }

    // Keep only current + previous for transition rendering.
    state[viewName] = [...previous, loaded].slice(-2);
    return state;
  });
}

function markFrameAvailable(
  viewName: string,
  frameIndex: number,
  mimeType: string,
  persisted: boolean,
): void {
  const runtime = getOrCreateRuntime(viewName);
  runtime.frameMimeTypes.set(frameIndex, mimeType);
  runtime.availableFrames.add(frameIndex);
  if (persisted) {
    runtime.persistedFrames.add(frameIndex);
  }
  resolveFrameWaiters(viewName, frameIndex, true);
}

async function requestFrameRange(
  viewName: string,
  startFrame: number,
  batchSize: number,
  token = sessionVersion,
): Promise<void> {
  const runtime = getOrCreateRuntime(viewName);
  const availableFrames = new Set<number>();
  try {
    const response = await requestWorker({
      type: "fetchChunk",
      viewName,
      startFrame,
      batchSize,
    });
    if (token !== sessionVersion) return;
    if (response.type !== "fetchChunk") return;

    for (const frame of response.frames) {
      availableFrames.add(frame.frameIndex);
      markFrameAvailable(viewName, frame.frameIndex, frame.mimeType, frame.persisted);
      if (shouldWarmDecode(frame.frameIndex)) {
        void decodeAndCacheFrame(viewName, frame.frameIndex);
      }
    }
  } catch (error) {
    if (token === sessionVersion) {
      console.warn(
        `Failed to fetch frame range ${startFrame}-${startFrame + batchSize - 1} for view ${viewName}:`,
        error,
      );
    }
  } finally {
    if (token === sessionVersion) {
      const endFrame = startFrame + batchSize;
      for (let frame = startFrame; frame < endFrame; frame++) {
        if (!availableFrames.has(frame) && !runtime.availableFrames.has(frame)) {
          resolveFrameWaiters(viewName, frame, false);
        }
      }
    }
  }
}

/**
 * Request one aligned chunk from backend as a progressive stream.
 *
 * Flow per frame:
 * network chunk -> OPFS write -> waiter resolve -> optional warm decode.
 */
async function requestChunk(viewName: string, chunkIndex: number, token = sessionVersion): Promise<void> {
  const runtime = getOrCreateRuntime(viewName);
  const range = getChunkRange(chunkIndex);
  if (!range) return;

  if (runtime.completedChunks.has(chunkIndex)) return;
  const inflight = runtime.inflightChunks.get(chunkIndex);
  if (inflight !== undefined) {
    await inflight;
    return;
  }

  const { startFrame, batchSize } = range;
  const chunkPromise = (async () => {
    const availableFrames = new Set<number>();
    try {
      const response = await requestWorker({
        type: "fetchChunk",
        viewName,
        startFrame,
        batchSize,
      });
      if (token !== sessionVersion) return;
      if (response.type !== "fetchChunk") return;

      for (const frame of response.frames) {
        availableFrames.add(frame.frameIndex);
        markFrameAvailable(viewName, frame.frameIndex, frame.mimeType, frame.persisted);
        if (shouldWarmDecode(frame.frameIndex)) {
          void decodeAndCacheFrame(viewName, frame.frameIndex);
        }
      }

      const endFrame = startFrame + batchSize;
      let isCompleteChunk = true;
      for (let frame = startFrame; frame < endFrame; frame++) {
        if (!runtime.availableFrames.has(frame)) {
          isCompleteChunk = false;
          break;
        }
      }

      if (token === sessionVersion && response.frames.length > 0 && isCompleteChunk) {
        runtime.completedChunks.add(chunkIndex);
      }
    } catch (error) {
      if (token === sessionVersion) {
        console.warn(`Failed to fetch frame chunk ${chunkIndex} for view ${viewName}:`, error);
      }
    } finally {
      if (token === sessionVersion) {
        const endFrame = startFrame + batchSize;
        for (let frame = startFrame; frame < endFrame; frame++) {
          if (!availableFrames.has(frame) && !runtime.availableFrames.has(frame)) {
            resolveFrameWaiters(viewName, frame, false);
          }
        }
      }
      runtime.inflightChunks.delete(chunkIndex);
    }
  })();

  runtime.inflightChunks.set(chunkIndex, chunkPromise);
  await chunkPromise;
}

/**
 * Ensure one frame is immediately available for rendering.
 *
 * Lookup order:
 * 1) in-memory LRU (fastest)
 * 2) OPFS (disk)
 * 3) network chunk stream (then OPFS)
 */
async function ensureFrameReady(viewName: string, frameIndex: number): Promise<LoadedImage | undefined> {
  const key = frameKey(viewName, frameIndex);
  const inMemory = decodedFrameCache.get(key);
  if (inMemory) return inMemory;

  const runtime = getOrCreateRuntime(viewName);
  if (runtime.availableFrames.has(frameIndex)) {
    const availableFrame = await decodeAndCacheFrame(viewName, frameIndex);
    if (availableFrame) {
      return availableFrame;
    }
    runtime.availableFrames.delete(frameIndex);
    runtime.persistedFrames.delete(frameIndex);
    runtime.frameMimeTypes.delete(frameIndex);
    runtime.completedChunks.delete(chunkForFrame(frameIndex));
  }

  const chunk = chunkForFrame(frameIndex);
  void requestChunk(viewName, chunk);

  const available = await waitForFrameAvailable(viewName, frameIndex);
  if (!available) return undefined;

  const loaded = await decodeAndCacheFrame(viewName, frameIndex);
  if (loaded) {
    return loaded;
  }

  runtime.availableFrames.delete(frameIndex);
  runtime.persistedFrames.delete(frameIndex);
  runtime.frameMimeTypes.delete(frameIndex);
  runtime.completedChunks.delete(chunk);
  return undefined;
}

function preloadAround(frameIndex: number): void {
  const total = getTotalFrames();
  if (total <= 0) return;

  const startWarm = Math.max(0, frameIndex - WARM_DECODE_BEHIND);
  const endWarm = Math.min(total - 1, frameIndex + WARM_DECODE_AHEAD);

  for (const viewName of videoViewNames.value) {
    const anchorChunk = chunkForFrame(frameIndex);

    for (let offset = 0; offset <= PREFETCH_CHUNKS_AHEAD; offset++) {
      void requestChunk(viewName, anchorChunk + offset);
    }
    for (let offset = 1; offset <= PREFETCH_CHUNKS_BEHIND; offset++) {
      void requestChunk(viewName, anchorChunk - offset);
    }

    const runtime = getOrCreateRuntime(viewName);
    for (let idx = startWarm; idx <= endWarm; idx++) {
      if (runtime.availableFrames.has(idx)) {
        void decodeAndCacheFrame(viewName, idx);
      }
    }
  }
}

function startBackgroundDownload(viewName: string, token = sessionVersion): void {
  if (backgroundDownloads.has(viewName)) return;

  const run = (async () => {
    const total = getTotalFrames();
    if (total <= 0) return;
    const maxChunk = Math.ceil(total / NETWORK_BATCH_SIZE) - 1;

    for (let chunk = 0; chunk <= maxChunk; chunk++) {
      if (token !== sessionVersion) return;
      await requestChunk(viewName, chunk, token);
    }
  })().finally(() => {
    backgroundDownloads.delete(viewName);
  });

  backgroundDownloads.set(viewName, run);
}

function canBackgroundDownload(viewName: string): boolean {
  const runtime = getOrCreateRuntime(viewName);
  // Background full-download only makes sense when frames persist on disk.
  // In memory-only fallback mode, this creates churn and evicts hot frames.
  return runtime.persistedFrames.size > 0;
}

async function ensureSessionReady(): Promise<number | undefined> {
  const ids = getSessionIdentifiers();
  if (!ids) return undefined;

  const sessionKey = `${ids.datasetId}:${ids.itemId}`;
  if (activeSessionKey === sessionKey) {
    return sessionVersion;
  }

  activeSessionKey = sessionKey;
  const token = sessionVersion;
  let response: FrameWorkerSuccessResponse;
  try {
    response = await requestWorker({
      type: "initSession",
      datasetId: ids.datasetId,
      itemId: ids.itemId,
      sessionToken: token,
    });
  } catch (error) {
    if (token === sessionVersion) {
      activeSessionKey = "";
    }
    throw error;
  }
  if (response.type !== "initSession") {
    if (token === sessionVersion) {
      activeSessionKey = "";
    }
    return undefined;
  }

  if (token !== sessionVersion) return undefined;

  for (const viewName of videoViewNames.value) {
    getOrCreateRuntime(viewName);
  }

  return token;
}

function resetFrameRuntime(): void {
  rejectPendingWorkerRequests(new Error("Video frame session was reset."));
  closeFrameWorker();
  workerRequestCounter = 0;
  sessionVersion += 1;
  activeSessionKey = "";

  resolveAllWaiters(false);
  viewRuntimes.clear();
  decodeInflight.clear();
  backgroundDownloads.clear();
  releaseImagesPerViewState();
  decodedFrameCache.clear();
  imagesPerView.value = {};
}

export const splitTrackInTwo = (
  track2split: Tracklet,
  prev: number,
  next: number,
): Annotation => {
  const rightTrackOrig = structuredClone(track2split);
  const { ui, ...noUIfieldsTrack } = rightTrackOrig;
  const rightTrack = new Tracklet(noUIfieldsTrack);
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

/**
 * Entry point called when video item context changes.
 * It tears down all in-flight network/decode tasks and resets caches.
 */
export const setBufferSpecs = () => {
  resetFrameRuntime();

  const viewCount = Math.max(videoViewNames.value.length, 1);
  decodedFrameCache = new LRUCache<string, LoadedImage>(
    BASE_MEMORY_CACHE_SIZE * viewCount,
    (_key, value) => {
      releaseLoadedImage(value);
    },
  );
};

/**
 * Load first renderable frame for every view, then continue full download in background.
 */
export async function loadInitialFrames(): Promise<void> {
  const totalFrames = getTotalFrames();
  const viewNames = videoViewNames.value;
  if (totalFrames <= 0 || viewNames.length === 0) return;

  const sessionToken = await ensureSessionReady();
  if (sessionToken === undefined) return;

  const firstFrameStatus = await Promise.all(
    viewNames.map(async (viewName) => {
      await requestFrameRange(viewName, 0, 1, sessionToken);
      let first = await ensureFrameReady(viewName, 0);
      if (!first) {
        await requestChunk(viewName, 0, sessionToken);
        first = await ensureFrameReady(viewName, 0);
      }
      if (sessionToken !== sessionVersion) return { viewName, loaded: false };
      if (first) {
        pushImageToCanvasView(viewName, first);
        return { viewName, loaded: true };
      }
      return { viewName, loaded: false };
    }),
  );

  if (sessionToken !== sessionVersion) return;
  if (!firstFrameStatus.every((status) => status.loaded)) {
    throw new Error("Failed to load the first frame for one or more video views.");
  }

  for (const status of firstFrameStatus) {
    if (!status.loaded) continue;
    if (canBackgroundDownload(status.viewName)) {
      startBackgroundDownload(status.viewName, sessionToken);
    }
  }

  preloadAround(0);
}

async function updateViewInternal(imageIndex: number): Promise<boolean> {
  if (lastFrameIndex.value === undefined) return false;

  const target = clampFrameIndex(imageIndex);
  const loadedFrames = await Promise.all(
    videoViewNames.value.map((viewName) => ensureFrameReady(viewName, target)),
  );

  for (let i = 0; i < videoViewNames.value.length; i++) {
    const loaded = loadedFrames[i];
    if (loaded) {
      pushImageToCanvasView(videoViewNames.value[i], loaded);
    }
  }

  preloadAround(target);
  return loadedFrames.every((loaded) => loaded !== undefined);
}

export async function updateViewAndWait(imageIndex: number): Promise<boolean> {
  return updateViewInternal(imageIndex);
}

export const updateView = (imageIndex: number): void => {
  void updateViewInternal(imageIndex);
};
