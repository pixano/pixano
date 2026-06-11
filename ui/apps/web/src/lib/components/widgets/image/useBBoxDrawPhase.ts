/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { buildBBoxCreate, generateShortId } from "$lib/annotations/buildPayloads.js";
import type {
  ImageWidgetOptions,
  ImageWidgetStorage,
  LocalBBox,
  ResourceMutation,
} from "$lib/annotations/types.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

import { BBOX_COLOR_DRAFT, getPixelFrame, PIXEL_THRESHOLD, pixelToNormalized } from "./imageWidgetGeometry.js";

export class BBoxDrawPhase {
  private draftRect: Konva.Rect | null = null;
  private draftOrigin: { x: number; y: number } | null = null;

  get isDrawing(): boolean {
    return this.draftRect !== null;
  }

  constructor(
    private readonly layer: Konva.Layer,
    private readonly stage: Konva.Stage,
    private readonly storage: ImageWidgetStorage,
    private readonly manager: WorkspaceManager,
    private readonly widgetId: string,
    private readonly imgOptions: ImageWidgetOptions,
    private readonly getKonvaImage: () => Konva.Image | null,
    private readonly onFinalized: () => void,
  ) {}

  beginDraw(event: Konva.KonvaEventObject<MouseEvent>): void {
    if (this.storage.mode !== "draw-bbox") return;
    event.cancelBubble = true;
    const pos = this.stage.getPointerPosition();
    if (!pos) return;
    this.draftOrigin = pos;
    this.draftRect = new Konva.Rect({
      x: pos.x,
      y: pos.y,
      width: 0,
      height: 0,
      stroke: BBOX_COLOR_DRAFT,
      strokeWidth: 2,
      dash: [6, 4],
      listening: false,
    });
    this.layer.add(this.draftRect);
    this.layer.batchDraw();
  }

  updateDraw(): void {
    if (!this.draftRect || !this.draftOrigin) return;
    const pos = this.stage.getPointerPosition();
    if (!pos) return;
    const x = Math.min(pos.x, this.draftOrigin.x);
    const y = Math.min(pos.y, this.draftOrigin.y);
    const w = Math.abs(pos.x - this.draftOrigin.x);
    const h = Math.abs(pos.y - this.draftOrigin.y);
    this.draftRect.position({ x, y });
    this.draftRect.width(w);
    this.draftRect.height(h);
    this.layer.batchDraw();
  }

  endDrawFinalize(): void {
    if (!this.draftRect || !this.draftOrigin) return;

    const rectX = this.draftRect.x();
    const rectY = this.draftRect.y();
    const width = this.draftRect.width();
    const height = this.draftRect.height();

    this.draftRect.destroy();
    this.draftRect = null;
    this.draftOrigin = null;
    this.layer.batchDraw();

    if (width < PIXEL_THRESHOLD || height < PIXEL_THRESHOLD) {
      this.storage.mode = "select";
      return;
    }

    const frame = getPixelFrame(this.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) {
      this.storage.mode = "select";
      return;
    }

    const clampedLeft = Math.max(frame.x, rectX);
    const clampedTop = Math.max(frame.y, rectY);
    const clampedRight = Math.min(frame.x + frame.w, rectX + width);
    const clampedBottom = Math.min(frame.y + frame.h, rectY + height);
    const clampedW = clampedRight - clampedLeft;
    const clampedH = clampedBottom - clampedTop;

    if (clampedW < PIXEL_THRESHOLD || clampedH < PIXEL_THRESHOLD) {
      this.storage.mode = "select";
      return;
    }

    const coordsNorm = pixelToNormalized(clampedLeft, clampedTop, clampedW, clampedH, frame);

    const localId = generateShortId();
    const { entityId, bboxId, mutations } = buildBBoxCreate(
      {
        datasetId: this.imgOptions.datasetId,
        recordId: this.imgOptions.recordId,
        viewId: this.imgOptions.viewId,
      },
      coordsNorm,
      { widgetId: this.widgetId, localBBoxId: localId },
    );
    void entityId;

    const bbox: LocalBBox = { id: localId, entityId, coordsNorm, persisted: false };
    this.storage.bboxes.push(bbox);

    for (const m of mutations) {
      if (m.op === "create" && m.resource === "bboxes") {
        (m as ResourceMutation & { body: Record<string, unknown> }).body.id = bboxId;
      }
      this.manager.queueMutation(m);
    }

    this.storage.mode = "select";
    this.storage.selectedId = localId;
    this.onFinalized();
  }

  cancelDraft(): void {
    if (this.draftRect) {
      this.draftRect.destroy();
      this.layer.batchDraw();
    }
    this.draftRect = null;
    this.draftOrigin = null;
    this.storage.mode = "select";
  }
}
