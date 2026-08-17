/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type Konva from "konva";
import { Tag } from "lucide-svelte";

import {
  CLASSIFY_TOOL_ID,
  HUMAN_CONFIDENCE,
  type ClassificationGeometry,
} from "./classificationTypes.js";
import type { LocalClassification } from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import { commitDraftWithEntity } from "$lib/annotations/payloadBuilders.js";
import type { Scene2DContext } from "$lib/annotations/scene/sceneContext.js";
import { DEFAULT_TOOL_2D, type Tool2D, type ToolHandler2D } from "$lib/annotations/scene/tool.js";
import { pickEntityLabel, type PendingEntityChoice } from "$lib/annotations/types.js";

/**
 * Tag the whole view with a class.
 *
 * There is no drag and no vertex to place: a classification says something
 * about the entire image, so the gesture is a single click anywhere on it,
 * which then asks for the class in the shared entity form. A click rather than
 * a bare toolbar press so the action stays repeatable and cancellable like
 * every other tool.
 *
 * The class name is taken from the entity the user picks — a new entity's
 * category, or the label of an existing one. That keeps one input for one
 * decision instead of asking twice for the same word, and it is why this tool
 * wraps `commitDraftWithEntity` rather than handing it the draft untouched:
 * the labels are only known once the entity choice comes back.
 */
class ClassifyHandler implements ToolHandler2D {
  constructor(private readonly ctx: Scene2DContext) {}

  onPointerDown(event: Konva.KonvaEventObject<MouseEvent>): void {
    event.cancelBubble = true;

    // Committed with no labels: the entity choice supplies them, and a draft
    // with an empty list is what `_labelsFor` fills in on confirm.
    const classification: LocalClassification = {
      id: generateShortId(),
      entityId: "",
      kind: "classification",
      viewId: this.ctx.buildContext.viewId,
      geometry: { labels: [], confidences: [] },
      persisted: false,
    };
    this.ctx.collection.add(classification);
    this.ctx.setActiveTool(DEFAULT_TOOL_2D);
    this.ctx.collection.select(classification.id);
    this.ctx.requestRedraw();

    this.ctx.beginPendingAnnotation({
      label: "classification",
      onConfirm: (choice) => this._confirm(classification, choice),
      onCancel: () => this._discardDraft(classification.id),
    });
  }

  onKeyDown(event: KeyboardEvent): boolean {
    if (event.key === "Escape") {
      this.ctx.setActiveTool(DEFAULT_TOOL_2D);
      return true;
    }
    return false;
  }

  /**
   * Fill the labels from the entity choice, then hand over to the shared
   * draft-commit. A choice that yields no usable label is dropped rather than
   * saved: the backend accepts an empty list, but a classification asserting
   * nothing is a row no one can act on.
   */
  private _confirm(classification: LocalClassification, choice: PendingEntityChoice): void {
    const label = this._labelFor(choice);
    if (!label) {
      this._discardDraft(classification.id);
      return;
    }
    const geometry: ClassificationGeometry = {
      labels: [label],
      confidences: [HUMAN_CONFIDENCE],
    };
    this.ctx.collection.setGeometry(classification.id, geometry);

    // Re-read so the builder sees the geometry that was just written.
    const committed = this.ctx.collection.find(classification.id);
    if (!committed) return;
    commitDraftWithEntity(committed, choice, this.ctx);
  }

  private _labelFor(choice: PendingEntityChoice): string {
    if (choice.mode === "new") return pickEntityLabel(choice.entityFields).trim();
    return pickEntityLabel(this.ctx.findEntity(choice.entityId)).trim();
  }

  private _discardDraft(localId: string): void {
    this.ctx.collection.remove(localId);
    this.ctx.requestRedraw();
  }
}

export const classifyTool: Tool2D = {
  id: CLASSIFY_TOOL_ID,
  label: "Classify the image (C)",
  icon: Tag,
  kind: "classification",
  cursor: "cell",
  createHandler: (ctx: Scene2DContext) => new ClassifyHandler(ctx),
};
