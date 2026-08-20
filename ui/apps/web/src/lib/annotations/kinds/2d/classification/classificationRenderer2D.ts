/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import { createClassificationEditor2D } from "./classificationEditor2D.js";
import {
  CLASSIFICATION_ID_ATTR,
  CLASSIFICATION_NODE_NAME,
  type ClassificationGeometry,
} from "./classificationTypes.js";
import type { LocalClassification } from "$lib/annotations/annotationCollection.svelte.js";
import type {
  AnnotationRenderer2D,
  AnnotationRenderer2DFactory,
} from "$lib/annotations/scene/renderer.js";
import {
  BBOX_COLOR_DRAFT,
  BBOX_COLOR_PERSISTED,
  getPixelFrame,
  type PixelFrame,
} from "$lib/annotations/scene/scene2dGeometry.js";
import type { Scene2DReadContext } from "$lib/annotations/scene/sceneContext.js";

const CHIP_MARGIN = 8;
const CHIP_HEIGHT = 22;
const CHIP_GAP = 4;
const CHIP_PADDING = 5;
const CHIP_FONT_SIZE = 12;
const CHIP_CORNER_RADIUS = 3;
const CHIP_TEXT_COLOR = "#0f172a";

/**
 * Displays the "classification" kind as chips stacked in the image's top-left
 * corner. This is the first kind with nothing spatial to draw: a classification
 * asserts something about the whole view, so it is pinned to the frame rather
 * than positioned within it.
 *
 * They are still drawn on the canvas rather than only in the side panel so the
 * kind behaves like every other one — visible where the annotating happens,
 * clickable to select, and subject to the same entity-visibility filter.
 */
class ClassificationRenderer2D implements AnnotationRenderer2D {
  readonly kind = "classification";

  private readonly groupById = new Map<string, Konva.Group>();

  constructor(private readonly ctx: Scene2DReadContext) {}

  sync(): void {
    const frame = getPixelFrame(this.ctx.getKonvaImage());
    const activeIds = new Set<string>();

    // Chips are stacked, so their vertical offset depends on how many visible
    // classifications precede them — hence the running index.
    let slot = 0;
    for (const classification of this.ctx.collection.byKind("classification")) {
      if (classification.persisted && !this.ctx.isEntityVisible(classification.entityId)) continue;
      if (!this._syncOne(classification, frame, slot)) continue;
      activeIds.add(classification.id);
      slot += 1;
    }

    for (const [id, group] of this.groupById) {
      if (!activeIds.has(id)) {
        group.destroy();
        this.groupById.delete(id);
      }
    }

    this.ctx.annotationLayer.batchDraw();
  }

  private _syncOne(
    classification: LocalClassification,
    frame: PixelFrame | null,
    slot: number,
  ): boolean {
    if (!frame) return false;
    const text = this._chipText(classification.geometry);
    if (!text) return false;

    this.groupById.get(classification.id)?.destroy();

    const color = classification.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT;
    const group = new Konva.Group({
      x: frame.x + CHIP_MARGIN,
      y: frame.y + CHIP_MARGIN + slot * (CHIP_HEIGHT + CHIP_GAP),
      name: CLASSIFICATION_NODE_NAME,
    });
    group.setAttr(CLASSIFICATION_ID_ATTR, classification.id);
    // Selection is display state, not a queue mutation, so it stays here.
    group.on("click tap", (e) => {
      e.cancelBubble = true;
      this.ctx.collection.select(classification.id);
    });

    const label = new Konva.Label();
    label.add(new Konva.Tag({ fill: color, cornerRadius: CHIP_CORNER_RADIUS }));
    label.add(
      new Konva.Text({
        text,
        fontSize: CHIP_FONT_SIZE,
        fontFamily: "system-ui, sans-serif",
        fill: CHIP_TEXT_COLOR,
        padding: CHIP_PADDING,
      }),
    );
    group.add(label);

    this.ctx.annotationLayer.add(group);
    this.groupById.set(classification.id, group);
    return true;
  }

  /** All the labels of one classification, joined — they share a confidence row. */
  private _chipText(geometry: ClassificationGeometry): string {
    return geometry.labels.filter((label) => label.length > 0).join(", ");
  }

  /**
   * No-op: a classification is created inside this widget by its own tool and
   * has no in-progress geometry to mirror across widgets.
   */
  syncDraft(): void {}

  destroy(): void {
    for (const group of this.groupById.values()) group.destroy();
    this.groupById.clear();
  }
}

export const classificationRenderer2DFactory: AnnotationRenderer2DFactory = {
  kind: "classification",
  create: (ctx: Scene2DReadContext) => new ClassificationRenderer2D(ctx),
  // Not a drag: with no geometry, the only editable content is the class
  // name, so the editor reopens the entity form on double-click.
  createEditor: createClassificationEditor2D,
};
