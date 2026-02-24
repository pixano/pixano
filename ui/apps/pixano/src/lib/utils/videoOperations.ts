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
import { Track, type Annotation, type LoadedImage } from "$lib/types/dataset";
import { getPixanoSource } from "$lib/utils/entityLookupUtils";
import { loadViewEmbeddings } from "$lib/utils/embeddingOperations";
import { saveTo } from "$lib/utils/saveItemUtils";
import * as api from "$lib/api";

const NETWORK_BATCH_SIZE = 512;
const PREFETCH_CHUNKS_AHEAD = 2;
const PREFETCH_CHUNKS_BEHIND = 1;
const WARM_DECODE_AHEAD = 8;
const WARM_DECODE_BEHIND = 2;
const PLAYBACK_PREFETCH_TRIGGER = Math.floor(NETWORK_BATCH_SIZE * 0.25);
const PLAYBACK_EXTRA_PREFETCH_CHUNKS = 3;
const BASE_MEMORY_CACHE_SIZE = 96;
const CACHE_ROOT_DIR_NAME = "pixano-video-cache";

type ViewRuntime = {
  persistedFrames: Set<number>;
  frameMimeTypes: Map<number, string>;
  inflightChunks: Map<number, Promise<void>>;
  completedChunks: Set<number>;
};

type FrameWaiter = (available: boolean) => void;

class FrameDiskCache {
  private rootPromise: Promise<unknown> | null = null;
  private sessionDir = "";
  private frameWriteLocks = new Map<string, Promise<void>>();
  private cleanupQueue: Promise<void> = Promise.resolve();

  private sanitizeSegment(value: string): string {
    return value.replace(/[^a-zA-Z0-9._-]/g, "_");
  }

  private async getRoot(): Promise<FileSystemDirectoryHandle | null> {
    const storage = typeof navigator === "undefined" ? undefined : navigator.storage;
    if (!storage || typeof storage.getDirectory !== "function") {
      return null;
    }

    if (this.rootPromise === null) {
      this.rootPromise = storage.getDirectory().catch(() => null);
    }

    const value = await this.rootPromise;
    if (
      value &&
      typeof value === "object" &&
      "getDirectoryHandle" in value &&
      typeof value.getDirectoryHandle === "function"
    ) {
      return value as FileSystemDirectoryHandle;
    }
    return null;
  }

  private async getCacheRoot(create: boolean): Promise<FileSystemDirectoryHandle | null> {
    const root = await this.getRoot();
    if (!root) return null;
    try {
      return await root.getDirectoryHandle(CACHE_ROOT_DIR_NAME, { create });
    } catch {
      return null;
    }
  }

  private async waitForSessionWrites(sessionDir: string): Promise<void> {
    const pendingWrites = Array.from(this.frameWriteLocks.entries())
      .filter(([lockKey]) => lockKey.startsWith(`${sessionDir}/`))
      .map(([, writePromise]) => writePromise.catch(() => undefined));

    if (pendingWrites.length > 0) {
      await Promise.all(pendingWrites);
    }
  }

  private enqueueSessionCleanup(sessionDir: string): void {
    if (!sessionDir) return;
    this.cleanupQueue = this.cleanupQueue
      .then(async () => {
        await this.waitForSessionWrites(sessionDir);
        const cacheRoot = await this.getCacheRoot(false);
        if (!cacheRoot) return;
        try {
          await cacheRoot.removeEntry(sessionDir, { recursive: true });
        } catch {
          // No-op: directory may already be deleted.
        }
      })
      .catch(() => {
        // Keep queue alive even when a cleanup task fails.
      });
  }

  getSessionDir(): string {
    return this.sessionDir;
  }

  async resetSession(datasetId: string, itemId: string, sessionToken: number): Promise<void> {
    const previousSessionDir = this.sessionDir;
    this.sessionDir = `${this.sanitizeSegment(datasetId)}__${this.sanitizeSegment(itemId)}__s${sessionToken}`;

    const cacheRoot = await this.getCacheRoot(true);
    if (!cacheRoot) return;

    await cacheRoot.getDirectoryHandle(this.sessionDir, { create: true });

    // Clear previous video cache asynchronously so item switch is responsive.
    if (previousSessionDir && previousSessionDir !== this.sessionDir) {
      this.enqueueSessionCleanup(previousSessionDir);
    }
  }

  private async getViewDir(
    viewName: string,
    create: boolean,
    sessionDir = this.sessionDir,
  ): Promise<FileSystemDirectoryHandle | null> {
    if (!sessionDir) return null;
    const cacheRoot = await this.getCacheRoot(create);
    if (!cacheRoot) return null;

    try {
      const session = await cacheRoot.getDirectoryHandle(sessionDir, { create });
      return await session.getDirectoryHandle(this.sanitizeSegment(viewName), { create });
    } catch {
      return null;
    }
  }

  async writeFrame(
    viewName: string,
    frameIndex: number,
    frame: Blob,
    sessionDirOverride?: string,
  ): Promise<boolean> {
    const sessionDir = sessionDirOverride ?? this.sessionDir;
    if (!sessionDir) return false;

    const lockKey = `${sessionDir}/${viewName}/${frameIndex}`;
    const previous = this.frameWriteLocks.get(lockKey);

    const writePromise = (async () => {
      if (previous !== undefined) {
        try {
          await previous;
        } catch {
          // Continue; new write attempts can recover transient lock conflicts.
        }
      }

      let lastError: unknown;
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const viewDir = await this.getViewDir(viewName, true, sessionDir);
          if (!viewDir) return false;

          const fileHandle = await viewDir.getFileHandle(`${frameIndex}.bin`, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(frame);
          await writable.close();
          return true;
        } catch (error) {
          const isWriteLockError =
            error instanceof DOMException && error.name === "NoModificationAllowedError";
          const isQuotaError = error instanceof DOMException && error.name === "QuotaExceededError";

          if (isQuotaError) {
            return false;
          }

          if (!isWriteLockError || attempt === 3) {
            throw error;
          }
          lastError = error;
          await new Promise<void>((resolve) => {
            setTimeout(resolve, 20 * (attempt + 1));
          });
        }
      }

      if (lastError) {
        throw lastError;
      }
      return false;
    })();

    this.frameWriteLocks.set(lockKey, writePromise);
    let wrote = false;
    try {
      wrote = await writePromise;
    } finally {
      if (this.frameWriteLocks.get(lockKey) === writePromise) {
        this.frameWriteLocks.delete(lockKey);
      }
    }

    return wrote;
  }

  async readFrame(
    viewName: string,
    frameIndex: number,
    mimeType?: string,
    sessionDirOverride?: string,
  ): Promise<Blob | undefined> {
    const sessionDir = sessionDirOverride ?? this.sessionDir;
    const viewDir = await this.getViewDir(viewName, false, sessionDir);
    if (!viewDir) return undefined;

    try {
      const fileHandle = await viewDir.getFileHandle(`${frameIndex}.bin`);
      const file = await fileHandle.getFile();
      if (mimeType && !file.type) {
        return file.slice(0, file.size, mimeType);
      }
      return file;
    } catch {
      return undefined;
    }
  }
}

const frameDiskCache = new FrameDiskCache();
const viewRuntimes = new Map<string, ViewRuntime>();
const frameWaiters = new Map<string, Set<FrameWaiter>>();
const decodeInflight = new Map<string, Promise<LoadedImage | undefined>>();
const backgroundDownloads = new Map<string, Promise<void>>();

let decodedFrameCache = new LRUCache<string, LoadedImage>(BASE_MEMORY_CACHE_SIZE);
let sessionAbortController = new AbortController();
let sessionVersion = 0;
let activeSessionKey = "";

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

function waitForFramePersisted(viewName: string, frameIndex: number): Promise<boolean> {
  const runtime = getOrCreateRuntime(viewName);
  if (runtime.persistedFrames.has(frameIndex)) {
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

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function isQuotaExceededError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "QuotaExceededError";
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

function isFramePersistedInAllViews(frameIndex: number): boolean {
  const target = clampFrameIndex(frameIndex);
  const viewNames = videoViewNames.value;
  if (viewNames.length === 0) return false;

  for (const viewName of viewNames) {
    const runtime = getOrCreateRuntime(viewName);
    if (!runtime.persistedFrames.has(target)) {
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
    if (!runtime.persistedFrames.has(target)) {
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
    if (!isFramePersistedInAllViews(anchor + offset)) {
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
      if (runtime.persistedFrames.has(targetFrame)) return true;
      return waitForFramePersisted(viewName, targetFrame);
    }),
  );

  return ready.every(Boolean);
}

/**
 * Decode a frame Blob into an HTMLImageElement with safe object URL lifecycle.
 * The URL is revoked immediately after decode so memory can be reclaimed.
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
 * Read + decode frame from OPFS into the small in-memory LRU render cache.
 *
 * Memory policy:
 * - OPFS is the source of truth for long videos.
 * - LRU holds only recently rendered/adjacent frames to keep UI snappy.
 */
async function decodeAndCacheFrame(
  viewName: string,
  frameIndex: number,
  directBlob?: Blob,
): Promise<LoadedImage | undefined> {
  const key = frameKey(viewName, frameIndex);
  const inMemory = decodedFrameCache.get(key);
  if (inMemory) return inMemory;

  const inflight = decodeInflight.get(key);
  if (inflight !== undefined) return inflight;

  const decodePromise = (async () => {
    const runtime = getOrCreateRuntime(viewName);
    const sessionDir = frameDiskCache.getSessionDir();
    const blob =
      directBlob ??
      (await frameDiskCache.readFrame(
        viewName,
        frameIndex,
        runtime.frameMimeTypes.get(frameIndex),
        sessionDir,
      ));

    if (!blob) return undefined;

    const image = await blobToImage(blob);
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

function markFramePersisted(viewName: string, frameIndex: number, mimeType: string): void {
  const runtime = getOrCreateRuntime(viewName);
  runtime.persistedFrames.add(frameIndex);
  runtime.frameMimeTypes.set(frameIndex, mimeType);
  resolveFrameWaiters(viewName, frameIndex, true);
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
  const ids = getSessionIdentifiers();
  if (!range || !ids) return;

  if (runtime.completedChunks.has(chunkIndex)) return;
  const inflight = runtime.inflightChunks.get(chunkIndex);
  if (inflight !== undefined) {
    await inflight;
    return;
  }

  const { startFrame, batchSize } = range;
  const cacheSessionDir = frameDiskCache.getSessionDir();
  const chunkPromise = (async () => {
    let streamedFrameCount = 0;
    try {
      for await (const part of api.streamViewFrameBatch(
        ids.datasetId,
        viewName,
        ids.itemId,
        startFrame,
        batchSize,
        sessionAbortController.signal,
      )) {
        if (token !== sessionVersion) return;

        streamedFrameCount += 1;
        const hasFrameWaiter = frameWaiters.has(frameKey(viewName, part.frameIndex));
        const shouldDecodeNow = hasFrameWaiter || shouldWarmDecode(part.frameIndex);

        let persisted = false;
        try {
          persisted = await frameDiskCache.writeFrame(
            viewName,
            part.frameIndex,
            part.blob,
            cacheSessionDir,
          );
        } catch (error) {
          // Quota can still be reached after cleanup. Keep the UI functional
          // by serving the current frame from memory instead of failing hard.
          if (isQuotaExceededError(error)) {
            if (shouldDecodeNow) {
              const fallbackLoaded = await decodeAndCacheFrame(
                viewName,
                part.frameIndex,
                part.blob,
              );
              if (fallbackLoaded && hasFrameWaiter) {
                resolveFrameWaiters(viewName, part.frameIndex, true);
              }
            }
            continue;
          }
          throw error;
        }

        if (persisted) {
          markFramePersisted(viewName, part.frameIndex, part.contentType);
          if (shouldWarmDecode(part.frameIndex)) {
            void decodeAndCacheFrame(viewName, part.frameIndex, part.blob);
          }
          continue;
        }

        if (shouldDecodeNow) {
          const fallbackLoaded = await decodeAndCacheFrame(viewName, part.frameIndex, part.blob);
          if (fallbackLoaded && hasFrameWaiter) {
            resolveFrameWaiters(viewName, part.frameIndex, true);
          }
        }
      }

      const endFrame = startFrame + batchSize;
      let isCompleteChunk = true;
      for (let frame = startFrame; frame < endFrame; frame++) {
        if (!runtime.persistedFrames.has(frame)) {
          isCompleteChunk = false;
          break;
        }
      }

      if (token === sessionVersion && streamedFrameCount > 0 && isCompleteChunk) {
        runtime.completedChunks.add(chunkIndex);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        console.warn(`Failed to fetch frame chunk ${chunkIndex} for view ${viewName}:`, error);
      }
    } finally {
      if (token === sessionVersion) {
        const endFrame = startFrame + batchSize;
        for (let frame = startFrame; frame < endFrame; frame++) {
          if (!runtime.persistedFrames.has(frame)) {
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
  if (runtime.persistedFrames.has(frameIndex)) {
    const persistedFrame = await decodeAndCacheFrame(viewName, frameIndex);
    if (persistedFrame) {
      return persistedFrame;
    }
    runtime.persistedFrames.delete(frameIndex);
    runtime.frameMimeTypes.delete(frameIndex);
  }

  const chunk = chunkForFrame(frameIndex);
  void requestChunk(viewName, chunk);

  const available = await waitForFramePersisted(viewName, frameIndex);
  if (!available) return undefined;

  return decodeAndCacheFrame(viewName, frameIndex);
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
      if (runtime.persistedFrames.has(idx)) {
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

async function ensureSessionReady(): Promise<number | undefined> {
  const ids = getSessionIdentifiers();
  if (!ids) return undefined;

  const sessionKey = `${ids.datasetId}:${ids.itemId}`;
  if (activeSessionKey === sessionKey) {
    return sessionVersion;
  }

  activeSessionKey = sessionKey;
  const token = sessionVersion;
  await frameDiskCache.resetSession(ids.datasetId, ids.itemId, token);

  if (token !== sessionVersion) return undefined;

  for (const viewName of videoViewNames.value) {
    getOrCreateRuntime(viewName);
  }

  return token;
}

function resetFrameRuntime(): void {
  sessionAbortController.abort();
  sessionAbortController = new AbortController();
  sessionVersion += 1;
  activeSessionKey = "";

  resolveAllWaiters(false);
  viewRuntimes.clear();
  decodeInflight.clear();
  backgroundDownloads.clear();
  decodedFrameCache.clear();
  imagesPerView.value = {};
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

/**
 * Entry point called when video item context changes.
 * It tears down all in-flight network/decode tasks and resets caches.
 */
export const setBufferSpecs = () => {
  resetFrameRuntime();

  const viewCount = Math.max(videoViewNames.value.length, 1);
  decodedFrameCache = new LRUCache<string, LoadedImage>(BASE_MEMORY_CACHE_SIZE * viewCount);
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
      void requestChunk(viewName, 0, sessionToken);
      let first = await ensureFrameReady(viewName, 0);
      if (!first) {
        await requestChunk(viewName, 0, sessionToken);
        first = await ensureFrameReady(viewName, 0);
      }
      if (sessionToken !== sessionVersion) return;
      if (first) {
        pushImageToCanvasView(viewName, first);
        startBackgroundDownload(viewName, sessionToken);
        return true;
      }
      return false;
    }),
  );

  if (sessionToken !== sessionVersion) return;
  if (!firstFrameStatus.every(Boolean)) {
    throw new Error("Failed to load the first frame for one or more video views.");
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
  loadViewEmbeddings(true);
  return loadedFrames.every((loaded) => loaded !== undefined);
}

export async function updateViewAndWait(imageIndex: number): Promise<boolean> {
  return updateViewInternal(imageIndex);
}

export const updateView = (imageIndex: number): void => {
  void updateViewInternal(imageIndex);
};
