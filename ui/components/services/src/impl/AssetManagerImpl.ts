/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AssetManager } from "../types";
import { LRUCache } from "./LRUCache";

const DEFAULT_CACHE_SIZE = 200;

/**
 * Asset loading with LRU caching and video frame preloading.
 *
 * Replaces ad-hoc image loading throughout the codebase.
 */
export class AssetManagerImpl implements AssetManager {
  private readonly imageCache: LRUCache<string, HTMLImageElement>;
  private readonly loadingPromises = new Map<string, Promise<HTMLImageElement>>();

  /** Map of viewName → array of frame URIs for video preloading. */
  private readonly frameUrisByView = new Map<string, string[]>();

  constructor(maxCacheSize: number = DEFAULT_CACHE_SIZE) {
    this.imageCache = new LRUCache(maxCacheSize);
  }

  async loadImage(uri: string): Promise<HTMLImageElement> {
    // Check cache
    const cached = this.imageCache.get(uri);
    if (cached) return cached;

    // Check if already loading
    const existing = this.loadingPromises.get(uri);
    if (existing) return existing;

    // Load the image
    const promise = this.doLoadImage(uri);
    this.loadingPromises.set(uri, promise);

    try {
      const img = await promise;
      this.imageCache.set(uri, img);
      return img;
    } finally {
      this.loadingPromises.delete(uri);
    }
  }

  async loadVideoFrame(viewName: string, frameIndex: number): Promise<HTMLImageElement> {
    const uris = this.frameUrisByView.get(viewName);
    if (!uris || frameIndex < 0 || frameIndex >= uris.length) {
      throw new Error(`Frame ${frameIndex} not available for view "${viewName}"`);
    }
    return this.loadImage(uris[frameIndex]);
  }

  preloadRange(viewName: string, startFrame: number, count: number): void {
    const uris = this.frameUrisByView.get(viewName);
    if (!uris) return;

    const end = Math.min(startFrame + count, uris.length);
    for (let i = startFrame; i < end; i++) {
      const uri = uris[i];
      if (!this.imageCache.has(uri) && !this.loadingPromises.has(uri)) {
        // Fire and forget — preloading is best-effort
        void this.loadImage(uri);
      }
    }
  }

  /** Register frame URIs for a video view (called during document loading). */
  registerVideoFrames(viewName: string, uris: string[]): void {
    this.frameUrisByView.set(viewName, uris);
  }

  evict(uri: string): void {
    this.imageCache.delete(uri);
  }

  clearCache(): void {
    this.imageCache.clear();
    this.frameUrisByView.clear();
  }

  get cacheSize(): number {
    return this.imageCache.size;
  }

  private doLoadImage(uri: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`Failed to load image: ${uri}`));
      img.src = uri;
    });
  }
}
