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
import type { SeamContext, StagedWorkFlag } from "$lib/annotations/scene/sceneContext.js";
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
 * nothing (`sameValue`). A box a save reads back comes rounded to float32 — a
 * move queued at x = 1.1 returns at 1.100000023841858 — and that echo of the
 * box's own numbers is not a change; no gizmo moves a box by so little.
 */
function sameAsStored(staged: readonly number[] | undefined, held: readonly number[]): boolean {
  return staged !== undefined && sameValue(staged, held);
}

/**
 * Per-widget editing session for the bbox3d tool: holds the transient confirm
 * state and gizmo visibility, and owns the commit. It lives in the kind (not the
 * host widget) so `PointCloudWidget` stays annotation-kind-agnostic (DEBT-5).
 * The editor reports drafts in; the HUD drives save/cancel/gizmo out.
 *
 * While the HUD holds a new box or a moved one, the session raises its
 * staged-work flag, so the workspace knows the record is not all saved — "Save
 * & next" would otherwise leave it, and the edit with it. Every way out of the
 * HUD lowers it, and the record's Discard takes the way out a Cancel takes.
 *
 * A gizmo drag — a move, a resize, a turn — holds the flag too, from its start
 * to its end, as a 2D shape's drag does, whatever the HUD held when it began: a
 * box a click only opened is work under way once a gizmo moves it. So "Save &
 * next" stays on the record while it runs, the record counts it as unsaved, and
 * a Discard during it drops it with the HUD: let go afterwards, it stages
 * nothing. One flag for the HUD and its drags, since both are the one box.
 *
 * A HUD holding nothing of its own — a box a click opened, maybe one whose move
 * is queued — shows the box as the record holds it, and closes once that box
 * changes under it (`letGoOfChangedBox`): Discard reaches only raised flags.
 * Its own box read back, rounded as the dataset stores it, is no change, and a
 * gizmo drag under way is let end before the HUD is judged. Any HUD, holding
 * work or not, closes once its box is deleted elsewhere.
 */
export class BBox3DSession {
  gizmoVisibility = $state<GizmoVisibility>({
    rings: true,
    resizeArrows: true,
    translateArrows: true,
  });
  confirm = $state<PendingConfirm | null>(null);

  private resetEditor: () => void = () => {};
  /**
   * Whether one of the editor's gizmo drags is under way: from the drag's
   * start (`reportDragStarted`) to its end, which the editor reports as it
   * reports a box (`reportReady`) or a draw canceled (`reportCanceled`).
   * Reactive, so that `letGoOfChangedBox`, run in an effect, runs again once
   * the drag is over.
   */
  private dragging = $state(false);
  /** Raised while the HUD holds a box that saving would write, or a gizmo drag runs. */
  private readonly staged: StagedWorkFlag | undefined;
  /** Whether the HUD holds a box that saving would write. */
  private holdsWork = false;

  constructor(private readonly seam: SeamContext) {
    this.staged = seam.claimStagedWork?.(() => this.cancel());
  }

  /** The overlay's editor registers how to clear its in-progress draft. */
  setResetEditor(reset: () => void): void {
    this.resetEditor = reset;
  }

  /**
   * Editor reports a draft ready to confirm: a box placed or opened, or the box
   * a gizmo drag leaves as it ends.
   */
  reportReady(coords: Coords3D, rotation?: Rotation3x3, editingId?: string): void {
    this.confirm = { coords, rotation, editingId };
    this.dragging = false;
    this.holdsWork = this.holdsUnsavedWork();
    this.updateStaged();
  }

  /**
   * Editor reports a gizmo drag begins on the box the HUD shows: the flag is
   * raised until the drag ends, whether or not the HUD held work of its own.
   */
  reportDragStarted(): void {
    this.dragging = true;
    this.updateStaged();
  }

  /** Editor reports its draft was canceled/cleared — or its editor is gone. */
  reportCanceled(): void {
    this.closeConfirm();
  }

  /**
   * Broadcast the in-progress geometry (called on every pointer move) so other
   * widgets can preview the gesture live — e.g. image widgets re-projecting the
   * box while it is dragged. Always publishes a fresh object: consumers track
   * the `$state` reassignment, so mutating a draft in place would go unnoticed.
   */
  reportPreview(coords: Coords3D, rotation?: Rotation3x3, editingId?: string): void {
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
   * names it so; and nothing is done to it while "Save & next" runs, when no
   * decision is taken.
   */
  get editingDeleteGesture(): DeleteGesture {
    const editingId = this.confirm?.editingId;
    const annotation = editingId ? this.seam.collection.find(editingId) : undefined;
    return annotation ? deleteGestureFor(annotation, this.seam.mutations) : "delete";
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
    this.closeConfirm();

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
    this.closeConfirm();
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
    // No decision is taken while "Save & next" runs: the HUD stays open, with
    // the box it holds, rather than closing on a delete that never happened.
    if (this.editingDeleteGesture === "locked") return;
    const annotation = this.seam.collection.find(editingId);
    if (annotation) {
      deleteLocalAnnotation(
        annotation,
        this.seam.collection,
        this.seam.mutations,
        this.seam.widgetId,
      );
    }
    this.closeConfirm();
    this.resetEditor();
  }

  /** Discard the pending draft and clear the editor. */
  cancel(): void {
    this.closeConfirm();
    this.resetEditor();
  }

  /**
   * Close the HUD once the box it shows is no longer the box the record holds.
   *
   * A box deleted elsewhere — by a Delete, or by a Reject in the Review tab —
   * closes the HUD whatever it holds: a move of its own has no box left to be
   * saved on, and its raised flag would go on counting, and keeping "Save &
   * next" on the record for, work that is gone.
   *
   * A HUD holding nothing of its own closes too once Discard puts its box back
   * as stored. Such a HUD's flag is down, so Discard never reaches it; left
   * open, it would go on showing — and its Apply would queue again — a
   * geometry the record no longer has. A HUD holding a move of its own stays
   * open while its box is there: Discard cancels it through its flag, and a
   * save's read-back keeps it. A box read back as it was saved, rounded to the
   * float32 the dataset stores, has not changed (`sameAsStored`): the HUD
   * stays open on it.
   *
   * Nor is the HUD closed while a gizmo drag runs: the editor would drop to
   * idle under the pointer, and the drag would be lost. A drag holds the
   * flag, so Discard drops it, HUD and all; what can still change the box
   * under it is a save's read-back. Let go, the drag reports the box it leaves
   * (`reportReady`), which is judged then: the HUD's own work if it differs
   * from the box the record holds, nothing otherwise.
   *
   * Reads the HUD, the editor's drag and, past them, the box — whatever the
   * HUD holds — so a caller running it in an effect runs it again whenever
   * one of them changes.
   */
  letGoOfChangedBox(): void {
    const pending = this.confirm;
    if (!pending?.editingId || this.dragging) return;
    const box = this.boxBeingEdited(pending.editingId);
    if (box && (this.holdsWork || stagedGeometry(pending, box) === null)) return;
    this.cancel();
  }

  toggleGizmo(key: keyof GizmoVisibility): void {
    this.gizmoVisibility = { ...this.gizmoVisibility, [key]: !this.gizmoVisibility[key] };
  }

  /**
   * Close the HUD's confirm: whatever it held is saved or abandoned now, and
   * so is a drag still under way — the editor is reset with it, or is gone.
   */
  private closeConfirm(): void {
    this.confirm = null;
    this.holdsWork = false;
    this.dragging = false;
    this.updateStaged();
  }

  /**
   * Raise the flag while the HUD holds work or a gizmo drag runs, lower it
   * once neither does. Called as either changes, never as the pointer moves.
   */
  private updateStaged(): void {
    this.staged?.set(this.holdsWork || this.dragging);
  }

  /**
   * Whether saving would write something: a new box, or a box moved, resized
   * or turned. A click that only opened a box's HUD stages nothing.
   */
  private holdsUnsavedWork(): boolean {
    const pending = this.confirm;
    if (!pending) return false;
    if (!pending.editingId) return true;
    const box = this.boxBeingEdited(pending.editingId);
    return box !== undefined && stagedGeometry(pending, box) !== null;
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
