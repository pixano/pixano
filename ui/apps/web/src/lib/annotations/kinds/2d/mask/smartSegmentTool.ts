/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Wand2 } from "lucide-svelte";

import { SMART_SEGMENT_TOOL_ID, type MaskGeometry } from "./maskTypes.js";
import type { LocalMask } from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import { commitDraftWithEntity } from "$lib/annotations/payloadBuilders.js";
import {
  BBOX_COLOR_DRAFT,
  getPixelFrame,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { DEFAULT_TOOL_2D, type Tool2D, type ToolHandler2D } from "$lib/annotations/scene/tool.js";
import {
  generateImageMask,
  listInferenceModels,
  MASK_GENERATION_TASK,
  type InferenceMask,
} from "$lib/api/inference.js";

const PROMPT_RADIUS = 5;
const PROMPT_STROKE_WIDTH = 2;
const HINT_FONT_SIZE = 12;
const HINT_OFFSET = 14;
const POSITIVE_COLOR = "rgba(0, 200, 0, 0.9)";
const NEGATIVE_COLOR = "rgba(200, 0, 0, 0.9)";
const ERROR_COLOR = "#f87171";

/** A prompt point in the image's own pixel grid, as the model expects. */
interface PromptPoint {
  x: number;
  y: number;
  positive: boolean;
}

/**
 * The two calls this tool makes, injectable so its logic can be tested without
 * a live inference server (there is rarely one in development).
 */
export interface SegmentationBackend {
  listModels(task: string): Promise<{ name: string }[]>;
  segment(request: {
    model: string;
    datasetId: string;
    viewId: string;
    prompt: { points: [number, number][]; labels: (0 | 1)[] };
  }): Promise<InferenceMask[]>;
}

const httpSegmentationBackend: SegmentationBackend = {
  listModels: (task) => listInferenceModels(task),
  segment: (request) => generateImageMask(request),
};

/**
 * Prompt-driven segmentation: drop points on and off the object, then let a
 * SAM-style model turn them into a mask.
 *
 * It lives in the `mask` kind rather than in one of its own because it produces
 * nothing new — the result is an ordinary `mask` annotation, and reusing the
 * kind's geometry and payload builder is what keeps a second, subtly different
 * mask write-path from appearing.
 *
 * Inference runs **server-side** (`POST /inference/image_mask_generation`). The
 * legacy UI also shipped an in-browser ONNX SAM; not porting it leaves one code
 * path to reason about, at the cost of requiring a connected provider.
 *
 * Keyboard: `X` toggles include/exclude for the next point, `Backspace` removes
 * the last one, `Enter` runs the model, `Escape` cancels.
 */
export class SmartSegmentHandler implements ToolHandler2D {
  private prompts: PromptPoint[] = [];
  private positive = true;
  private busy = false;
  private error: string | null = null;
  private overlay: Konva.Group | null = null;

  constructor(
    private readonly ctx: Scene2DContext,
    private readonly backend: SegmentationBackend = httpSegmentationBackend,
  ) {}

  activate(): void {
    this._reset();
  }

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;
    if (this.busy) return;
    const frame = this._frame();
    if (!frame) return;
    const point = this._toImagePixels(frame);
    if (!point) return;
    this.prompts.push({ ...point, positive: this.positive });
    this.error = null;
    this._refreshOverlay();
  }

  onPointerMove(): void {
    // Redraw so the hint follows the cursor.
    if (!this.busy) this._refreshOverlay();
  }

  onKeyDown(event: KeyboardEvent): boolean {
    switch (event.key) {
      case "Escape":
        this._reset();
        this.ctx.setActiveTool(DEFAULT_TOOL_2D);
        return true;
      case "Enter":
        void this._segment();
        return true;
      case "x":
      case "X":
        this.positive = !this.positive;
        this._refreshOverlay();
        return true;
      case "Backspace":
        this.prompts.pop();
        this._refreshOverlay();
        return true;
      default:
        return false;
    }
  }

  deactivate(): void {
    this._reset();
  }

  // ─── Geometry ─────────────────────────────────────────────────────────────

  private _frame(): PixelFrame | null {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return null;
    if (this.ctx.camera.imageWidth <= 0 || this.ctx.camera.imageHeight <= 0) return null;
    return frame;
  }

  /**
   * Stage pointer → the image's own pixel grid. The model runs on the stored
   * image, so prompts must be expressed there rather than in display pixels or
   * in the [0,1] space the other 2D kinds use.
   */
  private _toImagePixels(frame: PixelFrame): { x: number; y: number } | null {
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return null;
    const { imageWidth, imageHeight } = this.ctx.camera;
    return {
      x: Math.min(imageWidth, Math.max(0, ((pos.x - frame.x) / frame.w) * imageWidth)),
      y: Math.min(imageHeight, Math.max(0, ((pos.y - frame.y) / frame.h) * imageHeight)),
    };
  }

  // ─── Inference ────────────────────────────────────────────────────────────

  /**
   * Turn the prompts into a mask. Every failure lands in `this.error` and stays
   * on screen with the prompts intact, so a missing provider or a model error
   * costs the user nothing and can be retried after fixing the cause.
   */
  private async _segment(): Promise<void> {
    if (this.busy || this.prompts.length === 0) return;
    // A prompt of only negative points describes nothing to segment.
    if (!this.prompts.some((p) => p.positive)) {
      this.error = "Add at least one include point";
      this._refreshOverlay();
      return;
    }

    this.busy = true;
    this.error = null;
    this._refreshOverlay();

    try {
      const models = await this.backend.listModels(MASK_GENERATION_TASK);
      const model = models[0]?.name;
      if (!model) {
        this.error = "No segmentation model connected";
        return;
      }

      const masks = await this.backend.segment({
        model,
        datasetId: this.ctx.buildContext.datasetId,
        viewId: this.ctx.buildContext.viewId,
        prompt: {
          points: this.prompts.map((p): [number, number] => [p.x, p.y]),
          labels: this.prompts.map((p): 0 | 1 => (p.positive ? 1 : 0)),
        },
      });

      const geometry = this._toGeometry(masks[0]);
      if (!geometry) {
        this.error = "The model returned no mask";
        return;
      }
      this._commit(geometry);
    } catch (cause) {
      this.error = cause instanceof Error ? cause.message : "Segmentation failed";
    } finally {
      this.busy = false;
      this._refreshOverlay();
    }
  }

  /** The server's `{size, counts}` is already this kind's geometry. */
  private _toGeometry(mask: InferenceMask | undefined): MaskGeometry | null {
    if (!mask) return null;
    const [height, width] = mask.size ?? [];
    if (!(height > 0) || !(width > 0)) return null;
    if (typeof mask.counts !== "string" || mask.counts.length === 0) return null;
    return { size: [height, width], counts: mask.counts };
  }

  // ─── Commit ───────────────────────────────────────────────────────────────

  private _commit(geometry: MaskGeometry): void {
    this._reset();

    const mask: LocalMask = {
      id: generateShortId(),
      entityId: "",
      kind: "mask",
      viewId: this.ctx.buildContext.viewId,
      geometry,
      persisted: false,
    };
    this.ctx.collection.add(mask);
    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(mask.id);
    this.ctx.requestRedraw();

    this.ctx.beginPendingAnnotation({
      label: "mask",
      onConfirm: (choice) => commitDraftWithEntity(mask, choice, this.ctx),
      onCancel: () => {
        this.ctx.collection.remove(mask.id);
        this.ctx.requestRedraw();
      },
    });
  }

  // ─── Overlay ──────────────────────────────────────────────────────────────

  private _refreshOverlay(): void {
    this.overlay?.destroy();
    this.overlay = null;

    const frame = this._frame();
    if (!frame) return;

    const group = new Konva.Group({ listening: false });
    const { imageWidth, imageHeight } = this.ctx.camera;

    for (const prompt of this.prompts) {
      group.add(
        new Konva.Circle({
          x: frame.x + (prompt.x / imageWidth) * frame.w,
          y: frame.y + (prompt.y / imageHeight) * frame.h,
          radius: PROMPT_RADIUS,
          stroke: prompt.positive ? POSITIVE_COLOR : NEGATIVE_COLOR,
          strokeWidth: PROMPT_STROKE_WIDTH,
          fill: prompt.positive ? POSITIVE_COLOR : "transparent",
        }),
      );
    }

    const pos = this.ctx.stage.getPointerPosition();
    if (pos) {
      group.add(
        new Konva.Text({
          x: pos.x + HINT_OFFSET,
          y: pos.y - HINT_OFFSET,
          text: this._hintText(),
          fontSize: HINT_FONT_SIZE,
          fontFamily: "system-ui, sans-serif",
          fill: this.error ? ERROR_COLOR : BBOX_COLOR_DRAFT,
        }),
      );
    }

    this.ctx.annotationLayer.add(group);
    this.overlay = group;
    this.ctx.annotationLayer.batchDraw();
  }

  private _hintText(): string {
    if (this.error) return `Smart segment: ${this.error}`;
    if (this.busy) return "Smart segment: running…";
    const mode = this.positive ? "include" : "exclude";
    if (this.prompts.length === 0)
      return `Smart segment: click to add an ${mode} point (X toggles)`;
    return `Smart segment: ${this.prompts.length} point(s), Enter to run`;
  }

  private _reset(): void {
    this.overlay?.destroy();
    this.overlay = null;
    this.prompts = [];
    this.positive = true;
    this.busy = false;
    this.error = null;
    this.ctx.annotationLayer.batchDraw();
  }
}

export const smartSegmentTool: Tool2D = {
  id: SMART_SEGMENT_TOOL_ID,
  label: "Smart segmentation (W)",
  icon: Wand2,
  kind: "mask",
  cursor: "crosshair",
  createHandler: (ctx: Scene2DContext) => new SmartSegmentHandler(ctx),
};
