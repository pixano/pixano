/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { FILTER_DEBOUNCE_MS } from "./konvaConstants";
import { FilterManager } from "./workers/filterManager";
import type { FilterParams } from "./workers/filterWorker";
import type { ImageFilters } from "$lib/types/shapeTypes";
import { equalizeHistogram } from "$lib/utils/imageLoadUtils";

export class CanvasFilterPipeline {
  private filterManager: FilterManager | null = null;
  private tempCanvas: HTMLCanvasElement | null = null;
  private tempCtx: CanvasRenderingContext2D | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private getImageNode: (viewName: string) => Konva.Image | undefined,
    private getCurrentImage: (viewName: string) => HTMLImageElement | ImageBitmap | undefined,
  ) {}

  init(): void {
    this.filterManager = new FilterManager((viewName, filteredCanvas) => {
      const image = this.getImageNode(viewName);
      if (image) {
        image.image(filteredCanvas);
        image.clearCache();
        image.getLayer()?.batchDraw();
      }
    });
  }

  applyFilters(filters: ImageFilters, viewNames: string[]): void {
    const workerFilters: FilterParams = {
      brightness: filters.brightness,
      contrast: filters.contrast,
      redRange: [...filters.redRange] as [number, number],
      greenRange: [...filters.greenRange] as [number, number],
      blueRange: [...filters.blueRange] as [number, number],
      equalizeHistogram: filters.equalizeHistogram,
    };

    for (const view_name of viewNames) {
      const image = this.getImageNode(view_name);
      if (!image) continue;

      // Try off-thread path via Web Worker
      if (this.filterManager) {
        const sourceElement = this.getCurrentImage(view_name);
        if (sourceElement) {
          if (!this.tempCanvas) {
            this.tempCanvas = document.createElement("canvas");
            this.tempCtx = this.tempCanvas.getContext("2d");
          }
          this.tempCanvas.width = sourceElement.width;
          this.tempCanvas.height = sourceElement.height;
          if (this.tempCtx) {
            this.tempCtx.drawImage(sourceElement, 0, 0);
            this.filterManager.applyFilters(view_name, this.tempCanvas, workerFilters);
            continue;
          }
        }
      }

      // Fallback: synchronous Konva filter pipeline
      const adjustChannels = CanvasFilterPipeline.createAdjustChannels(filters);
      const filtersList = [Konva.Filters.Brighten, Konva.Filters.Contrast, adjustChannels];
      if (filters.equalizeHistogram) filtersList.push(equalizeHistogram);

      image.filters(filtersList);
      image.brightness(filters.brightness);
      image.contrast(filters.contrast);
    }
  }

  scheduleFilters(filters: ImageFilters, viewNames: string[]): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    this.debounceTimer = setTimeout(
      () => this.applyFilters(filters, viewNames),
      FILTER_DEBOUNCE_MS,
    );
  }

  cancelPendingTimer(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }

  destroy(): void {
    this.cancelPendingTimer();
    this.filterManager?.destroy();
    this.filterManager = null;
  }

  private static createAdjustChannels(filters: ImageFilters) {
    return (imageData: ImageData): void => {
      const { data } = imageData;
      const redMin = filters.redRange[0];
      const redMax = filters.redRange[1];
      const greenMin = filters.greenRange[0];
      const greenMax = filters.greenRange[1];
      const blueMin = filters.blueRange[0];
      const blueMax = filters.blueRange[1];

      for (let i = 0; i < data.length; i += 4) {
        const red = data[i];
        const green = data[i + 1];
        const blue = data[i + 2];

        if (
          red < redMin ||
          red > redMax ||
          green < greenMin ||
          green > greenMax ||
          blue < blueMin ||
          blue > blueMax
        ) {
          data[i] = 0;
          data[i + 1] = 0;
          data[i + 2] = 0;
        }
      }
    };
  }
}
