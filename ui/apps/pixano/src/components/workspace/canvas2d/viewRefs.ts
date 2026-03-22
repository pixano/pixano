/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import type { SaveMaskShape, Shape } from "$lib/types/shapeTypes";

export type ViewGroupKind = "background" | "static" | "active";

export interface MaskRef {
  beginStroke(x: number, y: number): void;
  updateStroke(x: number, y: number): void;
  endStroke(): void;
  loadDraftFromMask(mask: SaveMaskShape): void;
  getMaskData(): Shape | null;
  clearCanvas(): void;
  destroy(): void;
}

export class ViewRefManager {
  backgroundViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  staticViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  activeViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  imageRefs: Record<string, Konva.Image> = {};
  scaleOnFirstLoad: Record<string, boolean> = {};
  viewReady: Record<string, boolean> = {};
  maskRefs: Record<string, MaskRef | undefined> = {};

  constructor(private getStage: () => Konva.Stage | undefined) {}

  resetViewFlags(viewNames: string[], enableRenderCache: boolean): void {
    this.scaleOnFirstLoad = {};
    this.viewReady = {};
    for (const view_name of viewNames) {
      this.scaleOnFirstLoad[view_name] = enableRenderCache;
      this.viewReady[view_name] = false;
    }
  }

  getViewGroup(view_name: string, kind: ViewGroupKind): Konva.Group | undefined {
    const stage = this.getStage();
    if (kind === "background") {
      return this.backgroundViewRefs[view_name]?.node ?? stage?.findOne(`#bg-${view_name}`);
    }
    if (kind === "static") {
      return this.staticViewRefs[view_name]?.node ?? stage?.findOne(`#static-${view_name}`);
    }
    return this.activeViewRefs[view_name]?.node ?? stage?.findOne(`#active-${view_name}`);
  }

  /** Main interaction group (pointer coordinate system for tools). */
  getViewLayer(view_name: string): Konva.Group | undefined {
    return this.getViewGroup(view_name, "active");
  }

  forEachLinkedViewGroup(view_name: string, callback: (group: Konva.Group) => void): void {
    const groups = [
      this.getViewGroup(view_name, "background"),
      this.getViewGroup(view_name, "static"),
      this.getViewGroup(view_name, "active"),
    ];
    for (const group of groups) {
      if (group) callback(group);
    }
  }

  syncLinkedViewGroupsFromActive(view_name: string): void {
    const active = this.getViewGroup(view_name, "active");
    if (!active) return;
    const x = active.x();
    const y = active.y();
    const scaleX = active.scaleX();
    const scaleY = active.scaleY();
    this.forEachLinkedViewGroup(view_name, (group) => {
      if (group === active) return;
      group.position({ x, y });
      group.scale({ x: scaleX, y: scaleY });
    });
  }

  applyViewTransform(view_name: string, transform: { x: number; y: number; scale: number }): void {
    this.forEachLinkedViewGroup(view_name, (group) => {
      group.scale({ x: transform.scale, y: transform.scale });
      group.position({ x: transform.x, y: transform.y });
    });
  }

  /** Get the image node for a view using cached ref (O(1)) with fallback. */
  getImageNode(view_name: string): Konva.Image | undefined {
    const stage = this.getStage();
    return this.imageRefs[view_name] ?? stage?.findOne(`#image-${view_name}`);
  }

  /** Register an image ref when image loads. */
  registerImageRef(view_name: string): void {
    const stage = this.getStage();
    const img: Konva.Image | undefined = stage?.findOne(`#image-${view_name}`);
    if (img) this.imageRefs[view_name] = img;
  }

  /**
   * Scale a view to fit its grid cell. Returns the computed zoom factor,
   * or null if the view is not ready.
   */
  scaleView(
    view_name: string,
    containerEl: HTMLElement,
    gridSize: { rows: number; cols: number },
    imagesPerView: Record<string, unknown[]>,
    getCurrentImage: (name: string) => HTMLImageElement | ImageBitmap | undefined,
  ): number | null {
    const hasAnyLayer =
      !!this.getViewGroup(view_name, "background") ||
      !!this.getViewGroup(view_name, "static") ||
      !!this.getViewGroup(view_name, "active");
    if (!hasAnyLayer) {
      return null;
    }

    // Calculate max dims for every image in the grid
    const maxWidth = containerEl.getBoundingClientRect().width / gridSize.cols;
    const maxHeight = containerEl.getBoundingClientRect().height / gridSize.rows;

    // Get view index
    const keys = Object.keys(imagesPerView);
    const i = keys.findIndex((view) => view === view_name);

    // Calculate view position in grid
    const gridPosition = {
      x: i % gridSize.cols,
      y: Math.floor(i / gridSize.cols),
    };

    // Fit stage
    const currentImage = getCurrentImage(view_name);
    if (!currentImage) {
      return null;
    }
    const scaleByHeight = maxHeight / currentImage.height;
    const scaleByWidth = maxWidth / currentImage.width;
    const scale = Math.min(scaleByWidth, scaleByHeight);

    // Center view
    const offsetX = (maxWidth - currentImage.width * scale) / 2 + gridPosition.x * maxWidth;
    const offsetY = (maxHeight - currentImage.height * scale) / 2 + gridPosition.y * maxHeight;
    this.applyViewTransform(view_name, { x: offsetX, y: offsetY, scale });
    return scale;
  }
}
