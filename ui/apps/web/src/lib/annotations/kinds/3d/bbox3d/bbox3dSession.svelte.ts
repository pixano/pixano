/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { GizmoVisibility } from "./bbox3dTypes.js";
import type {
  BBox3DGeometry,
  LocalBBox3DAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import { generateShortId } from "$lib/annotations/buildPayloads.js";
import {
  bboxTransform,
  threeBoxToLanceXYZWHD,
  threeQuaternionToLanceRotation,
} from "$lib/annotations/coordinateTransforms";
import {
  beginEntityReassign,
  commitDraftWithEntity,
  commitGeometryEdit,
  deleteGestureFor,
  deleteLocalAnnotation,
  sameValue,
  type DeleteGesture,
} from "$lib/annotations/payloadBuilders.js";
import type { SeamContext } from "$lib/annotations/scene/sceneContext.js";
import type { Rotation3x3 } from "$lib/annotations/types.js";

type Coords3D = [number, number, number, number, number, number];

/** A 3D box the editor has staged and is waiting for the user to confirm. */
export interface PendingConfirm {
  coords: Coords3D;
  rotation?: Rotation3x3;
  /** Set when editing an existing box; absent when creating a new one. */
  editingId?: string;
}

/**
 * A box as the editor stages it when a click opens it and nothing moves: its
 * geometry taken to three.js space and back, the way `BBox3DTool` hands boxes
 * to the editor and the editor reports them. The trip does not give back the
 * stored numbers — a rotation goes through a quaternion, corners become centre
 * and size — but it is the same trip every time, so a staged box equal to this
 * one (`sameAsStored`) is the box untouched.
 */
function asStagedUntouched(geometry: BBox3DGeometry): { coords: Coords3D; rotation: Rotation3x3 } {
  const { position, size, quaternion } = bboxTransform(geometry);
  return {
    coords: threeBoxToLanceXYZWHD(position, size),
    rotation: threeQuaternionToLanceRotation(quaternion),
  };
}

/**
 * Whether numbers the editor staged are those of the box, as the dataset keeps
 * them: equal within float32's precision, the rule that tells an edit changing
 * nothing (`sameValue`).
 */
function sameAsStored(staged: readonly number[] | undefined, held: readonly number[]): boolean {
  return staged !== undefined && sameValue(staged, held);
}

/**
 * Per-widget editing session for the bbox3d tool: holds the transient confirm
 * state and gizmo visibility, and owns the commit. It lives in the kind (not the
 * host widget) so `PointCloudWidget` stays annotation-kind-agnostic (DEBT-5).
 * The editor reports drafts in; the HUD drives save/cancel/gizmo out.
 */
export class BBox3DSession {
  gizmoVisibility = $state<GizmoVisibility>({
    rings: true,
    resizeArrows: true,
    translateArrows: true,
  });
  confirm = $state<PendingConfirm | null>(null);

  private resetEditor: () => void = () => {};

  constructor(private readonly seam: SeamContext) {}

  /** The overlay's editor registers how to clear its in-progress draft. */
  setResetEditor(reset: () => void): void {
    this.resetEditor = reset;
  }

  /** Editor reports a draft ready to confirm. */
  reportReady(
    coords: [number, number, number, number, number, number],
    rotation?: Rotation3x3,
    editingId?: string,
  ): void {
    this.confirm = { coords, rotation, editingId };
  }

  /** Editor reports its draft was canceled/cleared. */
  reportCanceled(): void {
    this.confirm = null;
  }

  /**
   * Broadcast the in-progress geometry (called on every pointer move) so other
   * widgets can preview the gesture live — e.g. image widgets re-projecting the
   * box while it is dragged. Always publishes a fresh object: consumers track
   * the `$state` reassignment, so mutating a draft in place would go unnoticed.
   */
  reportPreview(
    coords: [number, number, number, number, number, number],
    rotation?: Rotation3x3,
    editingId?: string,
  ): void {
    this.seam.liveDraft.publish({
      kind: "bbox3d",
      geometry: { coords, format: "xyzwhd", rotation },
      editingId: editingId ?? null,
    });
  }

  /**
   * Clear the broadcast preview. Safe to call from a mounting, idling or
   * unmounting widget: the seam clears only a draft this widget published, so
   * another widget's active gesture is never wiped.
   */
  clearPreview(): void {
    this.seam.liveDraft.clear();
  }

  /**
   * What the HUD's delete button does to the box being edited: a model's box is
   * rejected — deleted, as any box is (`deleteLocalAnnotation`) — so the button
   * names it so.
   */
  get editingDeleteGesture(): DeleteGesture {
    const editingId = this.confirm?.editingId;
    const annotation = editingId ? this.seam.collection.find(editingId) : undefined;
    return annotation ? deleteGestureFor(annotation) : "delete";
  }

  /**
   * The persisted annotation the confirm currently targets, if any. The HUD
   * consults it to offer entity reassignment (only meaningful once the box has
   * been saved and thus has an entity to move away from).
   */
  get editingPersisted(): boolean {
    const editingId = this.confirm?.editingId;
    if (!editingId) return false;
    return this.seam.collection.find(editingId)?.persisted ?? false;
  }

  /**
   * Commit the pending draft (create or edit) through the shared helpers. A box
   * opened and saved without being moved is left as it is: nothing is written,
   * so a model's box is not saved as a person's edit, which would accept it,
   * by a person who changed nothing. Saved here, a move joins the record's
   * unsaved work, not the dataset: a model's pending box still reads pending,
   * until the workspace's Save stores it accepted, or an Accept.
   */
  save(): void {
    const pending = this.confirm;
    if (!pending) return;
    this.confirm = null;

    if (pending.editingId) {
      const box = this.boxBeingEdited(pending.editingId);
      const geometry = box ? stagedGeometry(pending, box) : null;
      if (geometry) commitGeometryEdit(this.seam, pending.editingId, geometry);
      this.resetEditor();
      return;
    }

    // New box: show it right away as an unsaved draft, but defer its entity (and
    // the create mutations) until the user confirms the entity in the Inspector
    // form. Mirrors the 2D draw tool so both kinds share one commit path.
    const draft: LocalBBox3DAnnotation = {
      id: generateShortId(),
      entityId: "",
      kind: "bbox3d",
      viewId: this.seam.buildContext.viewId,
      geometry: { coords: pending.coords, format: "xyzwhd", rotation: pending.rotation },
      persisted: false,
    };
    this.seam.collection.add(draft);
    this.seam.requestRedraw();
    this.seam.beginPendingAnnotation({
      label: "3D box",
      onConfirm: (choice) => commitDraftWithEntity(draft, choice, this.seam),
      onCancel: () => this.seam.collection.remove(draft.id),
    });
    this.resetEditor();
  }

  /**
   * Reassign the box currently being edited to a different entity: reuse the
   * Inspector's entity picker, then move the box on confirm. The backend prunes
   * the previously attached entity if this leaves it orphaned.
   */
  changeEntity(): void {
    const editingId = this.confirm?.editingId;
    if (!editingId) return;
    const annotation = this.seam.collection.find(editingId);
    // Checked here as well as inside `beginEntityReassign`: this method tears
    // its own HUD down first, and a draft box would see the editor close for a
    // reassignment that was never going to happen.
    if (!annotation || !annotation.persisted) return;
    this.confirm = null;
    beginEntityReassign(annotation, this.seam, { label: "3D box entity" });
    this.resetEditor();
  }

  /**
   * Delete the box currently being edited — on a model's box, its Reject (its
   * orphaned entity is pruned server-side).
   */
  deleteBox(): void {
    const editingId = this.confirm?.editingId;
    if (!editingId) return;
    const annotation = this.seam.collection.find(editingId);
    if (annotation) {
      deleteLocalAnnotation(
        annotation,
        this.seam.collection,
        this.seam.mutations,
        this.seam.widgetId,
      );
    }
    this.confirm = null;
    this.resetEditor();
  }

  /** Discard the pending draft and clear the editor. */
  cancel(): void {
    this.confirm = null;
    this.resetEditor();
  }

  toggleGizmo(key: keyof GizmoVisibility): void {
    this.gizmoVisibility = { ...this.gizmoVisibility, [key]: !this.gizmoVisibility[key] };
  }

  private boxBeingEdited(id: string): LocalBBox3DAnnotation | undefined {
    const annotation = this.seam.collection.find(id);
    return annotation?.kind === "bbox3d" ? (annotation as LocalBBox3DAnnotation) : undefined;
  }
}

/**
 * The geometry saving the staged box writes, or null when the box is as it
 * stands — as the dataset keeps it (`sameAsStored`). Only what the gesture
 * changed is taken from the editor: a box moved or resized but not turned
 * keeps its own rotation, rather than the copy the editor's quaternion gives
 * back a few float digits away.
 */
function stagedGeometry(
  pending: PendingConfirm,
  box: LocalBBox3DAnnotation,
): BBox3DGeometry | null {
  const untouched = asStagedUntouched(box.geometry);
  const moved = !sameAsStored(pending.coords, untouched.coords);
  const turned = !sameAsStored(pending.rotation, untouched.rotation);
  if (!moved && !turned) return null;
  return {
    coords: pending.coords,
    format: "xyzwhd",
    rotation: turned ? pending.rotation : box.geometry.rotation,
  };
}
