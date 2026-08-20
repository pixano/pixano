/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";
import { Spline } from "lucide-svelte";

import {
  DEFAULT_KEYPOINT_TEMPLATE,
  KEYPOINT_TEMPLATES,
  type KeypointTemplate,
} from "./keypointsTemplates.js";
import {
  DRAW_KEYPOINTS_TOOL_ID,
  type KeypointsGeometry,
  type KeypointState,
} from "./keypointsTypes.js";
import type { LocalKeypoints } from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import { commitDraftWithEntity } from "$lib/annotations/payloadBuilders.js";
import { getPixelFrame, type PixelFrame } from "$lib/annotations/scene/scene2dGeometry.js";
import { BBOX_COLOR_DRAFT } from "$lib/annotations/scene/scene2dStyleConstants.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { DEFAULT_TOOL_2D, type Tool2D, type ToolHandler2D } from "$lib/annotations/scene/tool.js";

const PREVIEW_VERTEX_RADIUS = 4;
const PREVIEW_STROKE_WIDTH = 2;
const HINT_FONT_SIZE = 12;
const HINT_OFFSET_Y = 14;

/** A placed point, in normalized [0,1] image space. */
interface PlacedPoint {
  x: number;
  y: number;
  state: KeypointState;
}

/**
 * Place a skeleton one point at a time, guided by the active template: each
 * click drops the next point, and the skeleton commits once every point of the
 * template has been placed. This is the UX the legacy `KeypointToolFSM`
 * documented but never had wired up ("place keypoints one by one according to a
 * template"), so it is implemented here rather than ported.
 *
 * The template is what makes the gesture legible — a label tells you which
 * point you are placing ("eye left"), and the bones appear as soon as both of
 * their endpoints exist.
 *
 * Keyboard: `T` cycles templates (only before the first point, since the point
 * count would otherwise change mid-skeleton), `I` marks the next point
 * occluded, `Backspace` undoes the last point, `Escape` cancels.
 */
class DrawKeypointsHandler implements ToolHandler2D {
  private template: KeypointTemplate = DEFAULT_KEYPOINT_TEMPLATE;
  private placed: PlacedPoint[] = [];
  private nextState: KeypointState = "visible";
  private preview: Konva.Group | null = null;

  constructor(private readonly ctx: Scene2DContext) {}

  activate(): void {
    this._reset();
    this._refreshPreview();
  }

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;
    const frame = this._frame();
    if (!frame) return;
    const point = this._toNormalized(frame);
    if (!point) return;

    this.placed.push({ ...point, state: this.nextState });
    // The occluded flag applies to one point only; placing it resets the mode.
    this.nextState = "visible";
    this._refreshPreview();

    if (this.placed.length >= this.template.points.length) this._commit();
  }

  onPointerMove(): void {
    // Redraw so the "next point" hint follows the cursor.
    if (this.placed.length < this.template.points.length) this._refreshPreview();
  }

  onKeyDown(event: KeyboardEvent): boolean {
    switch (event.key) {
      case "Escape":
        this._reset();
        this.ctx.setActiveTool(DEFAULT_TOOL_2D);
        return true;
      case "Backspace":
        this.placed.pop();
        this._refreshPreview();
        return true;
      case "t":
      case "T":
        this._cycleTemplate();
        return true;
      case "i":
      case "I":
        this.nextState = this.nextState === "visible" ? "invisible" : "visible";
        this._refreshPreview();
        return true;
      default:
        return false;
    }
  }

  deactivate(): void {
    this._reset();
  }

  // ─── Template ─────────────────────────────────────────────────────────────

  /**
   * Switching template mid-skeleton would leave the placed points bound to a
   * different point count and different labels, so it is only allowed while
   * nothing has been placed.
   */
  private _cycleTemplate(): void {
    if (this.placed.length > 0) return;
    const index = KEYPOINT_TEMPLATES.indexOf(this.template);
    this.template = KEYPOINT_TEMPLATES[(index + 1) % KEYPOINT_TEMPLATES.length];
    this._refreshPreview();
  }

  // ─── Geometry ─────────────────────────────────────────────────────────────

  private _frame(): PixelFrame | null {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    if (!frame || frame.w <= 0 || frame.h <= 0) return null;
    return frame;
  }

  /**
   * Stage pointer → normalized image space, clamped to [0,1]: the backend
   * rejects negative coordinates, and a point outside the image is meaningless
   * anyway.
   */
  private _toNormalized(frame: PixelFrame): { x: number; y: number } | null {
    const pos = this.ctx.stage.getPointerPosition();
    if (!pos) return null;
    return {
      x: Math.min(1, Math.max(0, (pos.x - frame.x) / frame.w)),
      y: Math.min(1, Math.max(0, (pos.y - frame.y) / frame.h)),
    };
  }

  // ─── Preview ──────────────────────────────────────────────────────────────

  private _refreshPreview(): void {
    this.preview?.destroy();
    this.preview = null;

    const frame = this._frame();
    if (!frame) return;

    const group = new Konva.Group({ listening: false });
    const pixels = this.placed.map((p) => ({
      x: frame.x + p.x * frame.w,
      y: frame.y + p.y * frame.h,
    }));

    // A bone appears as soon as both of its endpoints are placed, so the
    // skeleton assembles itself as you go.
    for (const [from, to] of this.template.edges) {
      if (from >= pixels.length || to >= pixels.length) continue;
      group.add(
        new Konva.Line({
          points: [pixels[from].x, pixels[from].y, pixels[to].x, pixels[to].y],
          stroke: BBOX_COLOR_DRAFT,
          strokeWidth: PREVIEW_STROKE_WIDTH,
        }),
      );
    }

    for (const [index, pixel] of pixels.entries()) {
      group.add(
        new Konva.Circle({
          x: pixel.x,
          y: pixel.y,
          radius: PREVIEW_VERTEX_RADIUS,
          stroke: this.template.points[index]?.color ?? BBOX_COLOR_DRAFT,
          strokeWidth: PREVIEW_STROKE_WIDTH,
          fill: this.placed[index].state === "invisible" ? "transparent" : BBOX_COLOR_DRAFT,
        }),
      );
    }

    const hint = this._hintText();
    if (hint) {
      const pos = this.ctx.stage.getPointerPosition();
      if (pos) {
        group.add(
          new Konva.Text({
            x: pos.x + HINT_OFFSET_Y,
            y: pos.y - HINT_OFFSET_Y,
            text: hint,
            fontSize: HINT_FONT_SIZE,
            fontFamily: "system-ui, sans-serif",
            fill: BBOX_COLOR_DRAFT,
          }),
        );
      }
    }

    this.ctx.annotationLayer.add(group);
    this.preview = group;
    this.ctx.annotationLayer.batchDraw();
  }

  /** Which point the next click places, so the gesture is self-explaining. */
  private _hintText(): string | null {
    const next = this.template.points[this.placed.length];
    if (!next) return null;
    const occluded = this.nextState === "invisible" ? " (occluded)" : "";
    return `${this.template.label}: ${next.label}${occluded}`;
  }

  // ─── Commit ───────────────────────────────────────────────────────────────

  private _commit(): void {
    const geometry: KeypointsGeometry = {
      templateId: this.template.id,
      coords: this.placed.flatMap((p) => [p.x, p.y]),
      states: this.placed.map((p) => p.state),
    };
    this._reset();

    const skeleton: LocalKeypoints = {
      id: generateShortId(),
      entityId: "",
      kind: "keypoints",
      viewId: this.ctx.buildContext.viewId,
      geometry,
      persisted: false,
    };
    this.ctx.collection.add(skeleton);
    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(skeleton.id);
    this.ctx.requestRedraw();

    this.ctx.beginPendingAnnotation({
      label: "keypoints",
      onConfirm: (choice) => commitDraftWithEntity(skeleton, choice, this.ctx),
      onCancel: () => this._discardDraft(skeleton.id),
    });
  }

  private _discardDraft(localId: string): void {
    this.ctx.collection.remove(localId);
    this.ctx.requestRedraw();
  }

  private _reset(): void {
    this.preview?.destroy();
    this.preview = null;
    this.placed = [];
    this.nextState = "visible";
    this.ctx.annotationLayer.batchDraw();
  }
}

export const drawKeypointsTool: Tool2D = {
  id: DRAW_KEYPOINTS_TOOL_ID,
  label: "Place keypoints (K)",
  icon: Spline,
  kind: "keypoints",
  cursor: "crosshair",
  createHandler: (ctx: Scene2DContext) => new DrawKeypointsHandler(ctx),
};
