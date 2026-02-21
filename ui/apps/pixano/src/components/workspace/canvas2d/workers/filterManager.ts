/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { FilterParams, FilterWorkerMessage, FilterWorkerResult } from "./filterWorker";

/**
 * Manages a Web Worker for off-thread image filter computation.
 * Maintains a filtered HTMLCanvasElement per view and calls back when ready.
 */
export class FilterManager {
  private worker: Worker | null = null;
  private filteredCanvases: Map<string, HTMLCanvasElement> = new Map();
  private onFiltered: ((viewName: string, canvas: HTMLCanvasElement) => void) | null = null;
  private pendingRequests: Set<string> = new Set();

  constructor(onFiltered: (viewName: string, canvas: HTMLCanvasElement) => void) {
    this.onFiltered = onFiltered;
    this.worker = new Worker(new URL("./filterWorker.ts", import.meta.url), { type: "module" });
    this.worker.onmessage = (e: MessageEvent<FilterWorkerResult>) => {
      this.handleWorkerResult(e.data);
    };
  }

  /**
   * Request filter application for a view's image.
   * The source ImageData is transferred (zero-copy) to the worker.
   */
  applyFilters(viewName: string, sourceCanvas: HTMLCanvasElement, filters: FilterParams): void {
    if (!this.worker) return;

    const ctx = sourceCanvas.getContext("2d");
    if (!ctx) return;

    const imageData = ctx.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
    this.pendingRequests.add(viewName);

    const msg: FilterWorkerMessage = { imageData, filters, viewName };
    this.worker.postMessage(msg, [imageData.data.buffer]);
  }

  private handleWorkerResult(result: FilterWorkerResult): void {
    const { imageData, viewName } = result;
    this.pendingRequests.delete(viewName);

    let canvas = this.filteredCanvases.get(viewName);
    if (!canvas || canvas.width !== imageData.width || canvas.height !== imageData.height) {
      canvas = document.createElement("canvas");
      canvas.width = imageData.width;
      canvas.height = imageData.height;
      this.filteredCanvases.set(viewName, canvas);
    }

    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.putImageData(imageData, 0, 0);
    }

    if (this.onFiltered) {
      this.onFiltered(viewName, canvas);
    }
  }

  hasPending(viewName: string): boolean {
    return this.pendingRequests.has(viewName);
  }

  destroy(): void {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    this.filteredCanvases.clear();
    this.onFiltered = null;
  }
}
