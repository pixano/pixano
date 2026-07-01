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
  commitDraftWithEntity,
  commitGeometryEdit,
  deleteLocalAnnotation,
  reassignEntity,
} from "$lib/annotations/payloadBuilders.js";
import type { SceneContextBase } from "$lib/annotations/scene/sceneContext.js";

/** A 3D box the editor has staged and is waiting for the user to confirm. */
export interface PendingConfirm {
  coords: [number, number, number, number, number, number];
  rotation?: number[];
  /** Set when editing an existing box; absent when creating a new one. */
  editingId?: string;
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

  constructor(private readonly seam: SceneContextBase) {}

  /** The overlay's editor registers how to clear its in-progress draft. */
  setResetEditor(reset: () => void): void {
    this.resetEditor = reset;
  }

  /** Editor reports a draft ready to confirm. */
  reportReady(
    coords: [number, number, number, number, number, number],
    rotation?: number[],
    editingId?: string,
  ): void {
    this.confirm = { coords, rotation, editingId };
  }

  /** Editor reports its draft was canceled/cleared. */
  reportCanceled(): void {
    this.confirm = null;
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

  /** Commit the pending draft (create or edit) through the shared helpers. */
  save(): void {
    const pending = this.confirm;
    if (!pending) return;
    this.confirm = null;

    const geometry: BBox3DGeometry = {
      coords: pending.coords,
      format: "xyzwhd",
      rotation: pending.rotation,
    };

    if (pending.editingId) {
      commitGeometryEdit(this.seam, pending.editingId, geometry);
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
      geometry,
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
    if (!annotation || !annotation.persisted) return;
    this.confirm = null;
    this.seam.beginPendingAnnotation({
      label: "3D box entity",
      onConfirm: (choice) => reassignEntity(annotation, choice, this.seam),
      onCancel: () => {},
    });
    this.resetEditor();
  }

  /** Delete the box currently being edited (its orphaned entity is pruned server-side). */
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
}
