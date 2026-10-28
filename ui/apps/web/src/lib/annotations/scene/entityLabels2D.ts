/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import Konva from "konva";

import type { LocalAnnotation } from "../annotationCollection.svelte.js";
import { pickEntityLabel } from "../types.js";
import type { PixelPoint } from "./scene2dGeometry.js";
import { BBOX_COLOR_DRAFT, BBOX_COLOR_PERSISTED } from "./scene2dStyleConstants.js";

const LABEL_FONT_SIZE = 12;
const LABEL_PADDING = 3;
const LABEL_CORNER_RADIUS = 3;
const LABEL_TEXT_COLOR = "#0f172a";
/** Gap between a label's underside and the shape it names. */
const LABEL_GAP = 1;

/** Attributes holding what a label was built from, so a stale one is spotted. */
const LABEL_TEXT_ATTR = "pixanoLabelText";
const LABEL_FILL_ATTR = "pixanoLabelFill";

/** What one annotation's label says, and on which colour. */
interface LabelLook {
  text: string;
  fill: string;
}

/**
 * An annotation names its entity on the saved/unsaved colour. `null` when
 * there is nothing to say.
 */
function labelLookOf(annotation: LocalAnnotation): LabelLook | null {
  const entityText = pickEntityLabel(annotation.entity);
  if (!entityText) return null;
  return {
    text: entityText,
    fill: annotation.persisted ? BBOX_COLOR_PERSISTED : BBOX_COLOR_DRAFT,
  };
}

/** One annotation's label: what to write, and where to hang it. */
export interface EntityLabelEntry {
  /** Local annotation id — the key this label is reconciled by. */
  id: string;
  /** The annotation whose entity is being named. */
  annotation: LocalAnnotation;
  /** Top-left of the shape; the label sits just above it. */
  anchor: PixelPoint;
}

/**
 * Names the entity each annotation belongs to, on the canvas, for every kind.
 *
 * Shared rather than re-implemented per kind because the interesting parts are
 * not the drawing:
 *
 * - **Reconciliation.** An annotation can be moved to another entity, or
 *   saved, so a label built once and never revisited goes on naming the
 *   entity the shape left behind, or on wearing a draft's colour — invisible
 *   until a page reload. Each label carries the text and colour it was built
 *   from and is rebuilt when either changes.
 * - **Not every annotation gets one.** An entity with no usable label yields no
 *   node at all, rather than an empty chip.
 * - **Pruning.** Labels for annotations that disappeared are destroyed, or they
 *   accumulate over a session.
 *
 * Kinds supply only the anchor, because only they know where "above the shape"
 * is: a box's corner, a skeleton's topmost point, a ring's first vertex.
 */
export class EntityLabels2D {
  private readonly labelById = new Map<string, Konva.Label>();

  constructor(private readonly layer: Konva.Layer) {}

  /**
   * Reconcile the whole set in one pass: create what is new, rebuild what
   * changed entity or colour, reposition everything, destroy what is gone.
   */
  sync(entries: readonly EntityLabelEntry[]): void {
    const seen = new Set<string>();

    for (const entry of entries) {
      const look = labelLookOf(entry.annotation);
      if (!look) continue;
      seen.add(entry.id);

      let label = this.labelById.get(entry.id);
      if (
        label &&
        (label.getAttr(LABEL_TEXT_ATTR) !== look.text ||
          label.getAttr(LABEL_FILL_ATTR) !== look.fill)
      ) {
        label.destroy();
        this.labelById.delete(entry.id);
        label = undefined;
      }
      if (!label) {
        label = this._make(look);
        this.layer.add(label);
        this.labelById.set(entry.id, label);
      }
      this._place(label, entry.anchor);
    }

    for (const [id, label] of this.labelById) {
      if (!seen.has(id)) {
        label.destroy();
        this.labelById.delete(id);
      }
    }
  }

  /**
   * Move one label without a full reconcile — for pointer-rate updates while
   * its shape is being dragged, where rebuilding the set would be wasteful.
   */
  moveTo(id: string, anchor: PixelPoint): void {
    const label = this.labelById.get(id);
    if (label) this._place(label, anchor);
  }

  destroy(): void {
    for (const label of this.labelById.values()) label.destroy();
    this.labelById.clear();
  }

  private _place(label: Konva.Label, anchor: PixelPoint): void {
    label.position({ x: anchor.x, y: anchor.y - label.height() - LABEL_GAP });
  }

  private _make(look: LabelLook): Konva.Label {
    const label = new Konva.Label({ listening: false });
    // Stamped so `sync()` can tell whether the label still matches its entity
    // and colour without reaching into the Konva children to read them back.
    label.setAttr(LABEL_TEXT_ATTR, look.text);
    label.setAttr(LABEL_FILL_ATTR, look.fill);
    label.add(
      new Konva.Tag({
        fill: look.fill,
        cornerRadius: LABEL_CORNER_RADIUS,
      }),
    );
    label.add(
      new Konva.Text({
        text: look.text,
        fontSize: LABEL_FONT_SIZE,
        fontFamily: "system-ui, sans-serif",
        fill: LABEL_TEXT_COLOR,
        padding: LABEL_PADDING,
      }),
    );
    return label;
  }
}
