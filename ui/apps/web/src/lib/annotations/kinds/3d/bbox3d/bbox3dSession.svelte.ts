/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBox3DGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { commitGeometryEdit, commitNewAnnotation } from "$lib/annotations/payloadBuilders.js";
import type { SceneContextBase } from "$lib/annotations/scene/sceneContext.js";

import type { GizmoVisibility } from "./bbox3dTypes.js";

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
    if (pending.editingId) commitGeometryEdit(this.seam, pending.editingId, geometry);
    else commitNewAnnotation(this.seam, "bbox3d", geometry);

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
