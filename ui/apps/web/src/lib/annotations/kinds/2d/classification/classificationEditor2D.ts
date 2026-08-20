/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";

import {
  CLASSIFICATION_ID_ATTR,
  CLASSIFICATION_NODE_NAME,
  HUMAN_CONFIDENCE,
  type ClassificationGeometry,
} from "./classificationTypes.js";
import { reassignEntity } from "$lib/annotations/payloadBuilders.js";
import type { AnnotationEditor2D } from "$lib/annotations/scene/renderer.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { pickEntityLabel, type PendingEntityChoice } from "$lib/annotations/types.js";

/**
 * Editing input for the "classification" kind: double-click a chip to change
 * the class it asserts.
 *
 * The odd one out among the editors, because the kind is: a classification has
 * no geometry, so there is nothing to drag and nothing a transformer could grab.
 * Its only mutable content is the class name — and that name is not stored
 * independently, it mirrors the parent entity's label (see `classifyTool`).
 * Re-classifying is therefore re-picking the entity, which is why this reopens
 * the same form creation uses instead of inventing a second way to type a class.
 *
 * Double-click, not single: a single click already means "select", and a
 * classification chip is the one annotation you cannot select by its shape.
 */
class ClassificationEditor2D implements AnnotationEditor2D {
  readonly kind = "classification";

  constructor(private readonly ctx: Scene2DContext) {
    ctx.annotationLayer.on("dblclick.classification-edit dbltap.classification-edit", (e) =>
      this._onDoubleClick(e.target),
    );
  }

  /** No handles to move onto the selection — the chip itself is the target. */
  syncSelection(): void {}

  destroy(): void {
    this.ctx.annotationLayer.off("dblclick.classification-edit dbltap.classification-edit");
  }

  private _onDoubleClick(node: Konva.Node): void {
    // The chip is a group of Konva shapes, so the double-click lands on a child
    // (the tag or the text); walk up to whichever ancestor carries the id.
    const id = this._annotationIdOf(node);
    if (!id) return;
    const annotation = this.ctx.collection.find(id);
    if (!annotation) return;

    this.ctx.collection.select(id);
    this.ctx.beginPendingAnnotation({
      label: "classification",
      onConfirm: (choice) => this._reclassify(id, choice),
      // Cancelling an edit leaves the existing classification untouched —
      // unlike creation, there is no draft to discard.
      onCancel: () => this.ctx.requestRedraw(),
    });
  }

  private _annotationIdOf(node: Konva.Node): string | null {
    let current: Konva.Node | null = node;
    while (current) {
      if (current.name() === CLASSIFICATION_NODE_NAME) {
        return (current.getAttr(CLASSIFICATION_ID_ATTR) as string | undefined) ?? null;
      }
      current = current.getParent() as Konva.Node | null;
    }
    return null;
  }

  private _reclassify(id: string, choice: PendingEntityChoice): void {
    const label = this._labelFor(choice);
    // An empty class would leave a row asserting nothing; keep the old one.
    if (!label) return;

    const annotation = this.ctx.collection.find(id);
    if (!annotation) return;

    const geometry: ClassificationGeometry = { labels: [label], confidences: [HUMAN_CONFIDENCE] };
    // Written before the reassign, which re-reads the annotation to build its
    // update body — so one mutation carries both the new entity and the new
    // labels instead of two updates racing over the same row.
    this.ctx.collection.setGeometry(id, geometry);
    reassignEntity({ ...annotation, geometry }, choice, this.ctx);
    this.ctx.requestRedraw();
  }

  private _labelFor(choice: PendingEntityChoice): string {
    if (choice.mode === "new") return pickEntityLabel(choice.entityFields).trim();
    return pickEntityLabel(this.ctx.findEntity(choice.entityId)).trim();
  }
}

export function createClassificationEditor2D(ctx: Scene2DContext): AnnotationEditor2D {
  return new ClassificationEditor2D(ctx);
}
