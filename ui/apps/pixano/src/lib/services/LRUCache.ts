/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Simple LRU (Least Recently Used) cache with a configurable max size.
 * Used by AssetManager for image caching.
 */
export class LRUCache<K, V> {
  private readonly maxSize: number;
  private readonly onEvict?: (key: K, value: V) => void;
  private readonly cache = new Map<K, V>();

  constructor(maxSize: number, onEvict?: (key: K, value: V) => void) {
    this.maxSize = maxSize;
    this.onEvict = onEvict;
  }

  get(key: K): V | undefined {
    const value = this.cache.get(key);
    if (value !== undefined) {
      // Move to end (most recently used)
      this.cache.delete(key);
      this.cache.set(key, value);
    }
    return value;
  }

  set(key: K, value: V): void {
    // Delete first to reset position if exists
    this.cache.delete(key);

    // Evict least recently used if at capacity
    while (this.cache.size >= this.maxSize) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
      const oldest = this.cache.keys().next().value;
      if (oldest !== undefined) {
        const oldestValue = this.cache.get(oldest);
        this.cache.delete(oldest);
        if (oldestValue !== undefined) {
          this.onEvict?.(oldest, oldestValue);
        }
      }
    }

    this.cache.set(key, value);
  }

  has(key: K): boolean {
    return this.cache.has(key);
  }

  delete(key: K): boolean {
    const value = this.cache.get(key);
    const deleted = this.cache.delete(key);
    if (deleted && value !== undefined) {
      this.onEvict?.(key, value);
    }
    return deleted;
  }

  clear(): void {
    if (this.onEvict) {
      for (const [key, value] of this.cache) {
        this.onEvict(key, value);
      }
    }
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }
}
