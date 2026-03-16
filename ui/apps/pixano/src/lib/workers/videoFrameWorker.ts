/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { streamViewFrameBatch } from "../api/viewsApi";

const CACHE_ROOT_DIR_NAME = "pixano-video-cache";
const MEMORY_FALLBACK_MAX_ITEMS = 768;
const MEMORY_FALLBACK_MAX_BYTES = 256 * 1024 * 1024;

function getErrorMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return "";
}

function isStorageQuotaLikeError(error: unknown): boolean {
  const message = getErrorMessage(error);
  if (error instanceof DOMException) {
    if (error.name === "QuotaExceededError") return true;
    if (error.name === "UnknownError" && /quota|storage|space|exceed/i.test(message)) return true;
    if (error.name === "InvalidStateError" && /quota|storage|space|exceed/i.test(message))
      return true;
  }
  return /storage quota|exceed(?:ed|s|ing)?.*quota|insufficient.*storage/i.test(message);
}

type InitSessionRequest = {
  requestId: number;
  type: "initSession";
  datasetId: string;
  itemId: string;
  sessionToken: number;
};

type FetchChunkRequest = {
  requestId: number;
  type: "fetchChunk";
  viewName: string;
  startFrame: number;
  batchSize: number;
};

type DecodeFrameRequest = {
  requestId: number;
  type: "decodeFrame";
  viewName: string;
  frameIndex: number;
  mimeType?: string;
};

type ClearSessionRequest = {
  requestId: number;
  type: "clearSession";
};

type WorkerRequest =
  | InitSessionRequest
  | FetchChunkRequest
  | DecodeFrameRequest
  | ClearSessionRequest;

type FetchChunkFrameResult = {
  frameIndex: number;
  mimeType: string;
  persisted: boolean;
};

type WorkerResponse =
  | { requestId: number; ok: true; type: "initSession" }
  | { requestId: number; ok: true; type: "clearSession" }
  | { requestId: number; ok: true; type: "fetchChunk"; frames: FetchChunkFrameResult[] }
  | { requestId: number; ok: true; type: "decodeFrame"; missing: true }
  | { requestId: number; ok: true; type: "decodeFrame"; missing: false; bitmap: ImageBitmap }
  | { requestId: number; ok: false; type: WorkerRequest["type"]; error: string };

type SessionState = {
  datasetId: string;
  itemId: string;
};

class FrameDiskCache {
  private rootPromise: Promise<unknown> | null = null;
  private sessionDir = "";
  private frameWriteLocks = new Map<string, Promise<boolean>>();
  private cleanupQueue: Promise<void> = Promise.resolve();
  private diskCacheDisabled = false;

  private sanitizeSegment(value: string): string {
    return value.replace(/[^a-zA-Z0-9._-]/g, "_");
  }

  private disableDiskCache(): void {
    this.diskCacheDisabled = true;
    this.rootPromise = Promise.resolve(null);
  }

  private async getRoot(): Promise<FileSystemDirectoryHandle | null> {
    if (this.diskCacheDisabled) {
      return null;
    }

    const storage = typeof navigator === "undefined" ? undefined : navigator.storage;
    if (!storage || typeof storage.getDirectory !== "function") {
      return null;
    }

    if (this.rootPromise === null) {
      this.rootPromise = storage.getDirectory().catch((error) => {
        if (isStorageQuotaLikeError(error)) {
          this.disableDiskCache();
        }
        return null;
      });
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
    } catch (error) {
      if (create && isStorageQuotaLikeError(error)) {
        this.disableDiskCache();
      }
      return null;
    }
  }

  private async waitForSessionWrites(sessionDir: string): Promise<void> {
    const pendingWrites = Array.from(this.frameWriteLocks.entries())
      .filter(([lockKey]) => lockKey.startsWith(`${sessionDir}/`))
      .map(([, writePromise]) =>
        writePromise.catch((error: unknown) => {
          console.warn("[VideoFrameWorker] Pending frame write failed:", error);
          return undefined;
        }),
      );

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
      .catch((error: unknown) => {
        console.warn("[VideoFrameWorker] Session cleanup failed:", error);
      });
  }

  async resetSession(datasetId: string, itemId: string, sessionToken: number): Promise<void> {
    const previousSessionDir = this.sessionDir;
    this.sessionDir = `${this.sanitizeSegment(datasetId)}__${this.sanitizeSegment(itemId)}__s${sessionToken}`;

    const cacheRoot = await this.getCacheRoot(true);
    if (!cacheRoot) return;

    try {
      await cacheRoot.getDirectoryHandle(this.sessionDir, { create: true });
    } catch (error) {
      if (isStorageQuotaLikeError(error)) {
        this.disableDiskCache();
        return;
      }
      throw error;
    }

    if (previousSessionDir && previousSessionDir !== this.sessionDir) {
      this.enqueueSessionCleanup(previousSessionDir);
    }
  }

  private async getViewDir(
    viewName: string,
    create: boolean,
  ): Promise<FileSystemDirectoryHandle | null> {
    if (!this.sessionDir) return null;
    const cacheRoot = await this.getCacheRoot(create);
    if (!cacheRoot) return null;

    try {
      const session = await cacheRoot.getDirectoryHandle(this.sessionDir, { create });
      return await session.getDirectoryHandle(this.sanitizeSegment(viewName), { create });
    } catch (error) {
      if (create && isStorageQuotaLikeError(error)) {
        this.disableDiskCache();
      }
      return null;
    }
  }

  async writeFrame(viewName: string, frameIndex: number, frame: Blob): Promise<boolean> {
    if (!this.sessionDir) return false;

    const lockKey = `${this.sessionDir}/${viewName}/${frameIndex}`;
    const previous = this.frameWriteLocks.get(lockKey);

    const writePromise = (async () => {
      if (previous !== undefined) {
        try {
          await previous;
        } catch {
          // Continue; new write attempts can recover transient lock conflicts.
        }
      }

      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const viewDir = await this.getViewDir(viewName, true);
          if (!viewDir) return false;

          const fileHandle = await viewDir.getFileHandle(`${frameIndex}.bin`, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(frame);
          await writable.close();
          return true;
        } catch (error) {
          const isWriteLockError =
            error instanceof DOMException && error.name === "NoModificationAllowedError";
          const isQuotaError = isStorageQuotaLikeError(error);

          if (isQuotaError) {
            this.disableDiskCache();
            return false;
          }

          if (!isWriteLockError || attempt === 3) {
            throw error;
          }

          await new Promise<void>((resolve) => {
            setTimeout(resolve, 20 * (attempt + 1));
          });
        }
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
  ): Promise<Blob | undefined> {
    if (this.diskCacheDisabled) return undefined;

    const viewDir = await this.getViewDir(viewName, false);
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

const worker = self as unknown as {
  postMessage: (message: WorkerResponse, transfer?: Transferable[]) => void;
  onmessage: ((event: MessageEvent<WorkerRequest>) => void) | null;
};
const frameDiskCache = new FrameDiskCache();
let session: SessionState | null = null;
let sessionAbortController = new AbortController();
const chunkInflight = new Map<string, Promise<FetchChunkFrameResult[]>>();
type MemoryFallbackEntry = { blob: Blob; size: number };
const memoryFallback = new Map<string, MemoryFallbackEntry>();
let memoryFallbackBytes = 0;

function frameKey(viewName: string, frameIndex: number): string {
  return `${viewName}:${frameIndex}`;
}

function deleteMemoryFallbackEntry(key: string): void {
  const entry = memoryFallback.get(key);
  if (!entry) return;
  memoryFallback.delete(key);
  memoryFallbackBytes = Math.max(0, memoryFallbackBytes - entry.size);
}

function pushMemoryFallback(viewName: string, frameIndex: number, blob: Blob): void {
  const key = frameKey(viewName, frameIndex);
  deleteMemoryFallbackEntry(key);

  const nextSize = blob.size || 0;
  memoryFallback.set(key, { blob, size: nextSize });
  memoryFallbackBytes += nextSize;

  while (
    memoryFallback.size > MEMORY_FALLBACK_MAX_ITEMS ||
    memoryFallbackBytes > MEMORY_FALLBACK_MAX_BYTES
  ) {
    const oldest = memoryFallback.keys().next();
    if (oldest.done) break;
    deleteMemoryFallbackEntry(oldest.value);
  }
}

function postResponse(response: WorkerResponse, transfer: Transferable[] = []): void {
  worker.postMessage(response, transfer);
}

function clearState(): void {
  sessionAbortController.abort();
  sessionAbortController = new AbortController();
  chunkInflight.clear();
  memoryFallback.clear();
  memoryFallbackBytes = 0;
}

async function handleInitSession(request: InitSessionRequest): Promise<void> {
  clearState();
  session = {
    datasetId: request.datasetId,
    itemId: request.itemId,
  };
  await frameDiskCache.resetSession(request.datasetId, request.itemId, request.sessionToken);
  postResponse({ requestId: request.requestId, ok: true, type: "initSession" });
}

async function handleFetchChunk(request: FetchChunkRequest): Promise<void> {
  if (!session) {
    throw new Error("Video frame session is not initialized.");
  }

  const chunkKey = `${request.viewName}:${request.startFrame}:${request.batchSize}`;
  const inflight = chunkInflight.get(chunkKey);
  if (inflight !== undefined) {
    const frames = await inflight;
    postResponse({ requestId: request.requestId, ok: true, type: "fetchChunk", frames });
    return;
  }

  const run = (async () => {
    const frames = new Map<number, FetchChunkFrameResult>();
    for await (const part of streamViewFrameBatch(
      session.datasetId,
      request.viewName,
      session.itemId,
      request.startFrame,
      request.batchSize,
      sessionAbortController.signal,
    )) {
      let persisted = false;
      try {
        persisted = await frameDiskCache.writeFrame(request.viewName, part.frameIndex, part.blob);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          throw error;
        }
      }

      if (!persisted) {
        pushMemoryFallback(request.viewName, part.frameIndex, part.blob);
      } else {
        deleteMemoryFallbackEntry(frameKey(request.viewName, part.frameIndex));
      }

      frames.set(part.frameIndex, {
        frameIndex: part.frameIndex,
        mimeType: part.contentType,
        persisted,
      });
    }
    return Array.from(frames.values()).sort((a, b) => a.frameIndex - b.frameIndex);
  })();

  chunkInflight.set(chunkKey, run);
  try {
    const frames = await run;
    postResponse({ requestId: request.requestId, ok: true, type: "fetchChunk", frames });
  } finally {
    if (chunkInflight.get(chunkKey) === run) {
      chunkInflight.delete(chunkKey);
    }
  }
}

async function decodeFrameBlob(
  viewName: string,
  frameIndex: number,
  mimeType?: string,
): Promise<Blob | undefined> {
  const inMemory = memoryFallback.get(frameKey(viewName, frameIndex));
  if (inMemory) return inMemory.blob;
  return frameDiskCache.readFrame(viewName, frameIndex, mimeType);
}

async function handleDecodeFrame(request: DecodeFrameRequest): Promise<void> {
  const blob = await decodeFrameBlob(request.viewName, request.frameIndex, request.mimeType);
  if (!blob) {
    postResponse({
      requestId: request.requestId,
      ok: true,
      type: "decodeFrame",
      missing: true,
    });
    return;
  }

  if (typeof createImageBitmap !== "function") {
    throw new Error("createImageBitmap is not available in worker scope.");
  }

  const bitmap = await createImageBitmap(blob);
  postResponse(
    {
      requestId: request.requestId,
      ok: true,
      type: "decodeFrame",
      missing: false,
      bitmap,
    },
    [bitmap],
  );
}

worker.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const request = event.data;
  const requestType = request.type;

  void (async () => {
    try {
      if (requestType === "initSession") {
        await handleInitSession(request);
        return;
      }
      if (requestType === "fetchChunk") {
        await handleFetchChunk(request);
        return;
      }
      if (requestType === "decodeFrame") {
        await handleDecodeFrame(request);
        return;
      }
      if (requestType === "clearSession") {
        clearState();
        session = null;
        postResponse({ requestId: request.requestId, ok: true, type: "clearSession" });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      postResponse({
        requestId: request.requestId,
        ok: false,
        type: requestType,
        error: message,
      });
    }
  })();
};
