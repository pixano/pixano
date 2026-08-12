/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetLayout } from "./datasetLayout.js";
import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { LiveAnnotationDraft } from "$lib/annotations/scene/sceneContext.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { FieldInfo } from "$lib/types/dataset.js";

/**
 * Reactive "what record is currently loaded?" state, shared by the
 * sub-services of the workspace.
 *
 * `RecordLoader` writes the selection at the start of each load;
 * `MutationQueue` reads it to know which dataset to target. Holding the
 * pair on a tiny shared object (rather than on `WorkspaceManager`) lets
 * each sub-service depend on this narrow type instead of the full manager
 * class.
 *
 * The annotation collection lives here because annotations are record-scoped
 * truth: every widget viewing the record reads and writes the same instance
 * (see docs/ARCHITECTURE_TOOLING.md, Phase 6).
 *
 * Lives in a `.svelte.ts` file so the runes compiler picks up `$state`.
 */
export class WorkspaceSession {
  datasetId = $state<string | null>(null);
  recordId = $state<string | null>(null);
  entities = $state<EntityRow[]>([]);
  entitySchemaName = $state<string | null>(null);
  /** Field definitions of the dataset's entity table, used to generate the entity form. */
  entitySchemaFields = $state<Record<string, FieldInfo> | null>(null);
  /** Shared annotations of the loaded record; replaced on every load. */
  annotations = $state(new AnnotationCollection());
  /**
   * Entity ids whose annotations are currently shown. `null` means "all
   * visible" (the default). A set isolates the listed entities. Record-scoped
   * shared state so every widget viewing the record filters identically.
   */
  visibleEntityIds = $state<Set<string> | null>(null);
  /**
   * In-progress geometry the active editing gesture broadcasts on every pointer
   * move, so widgets in other mediums can preview it live (e.g. re-projecting a
   * 3D box onto images while it is dragged). Committed truth stays in
   * `annotations`; this slot is null whenever no gesture is running.
   */
  liveDraft = $state<LiveAnnotationDraft | null>(null);
  /**
   * The arrangement this record opened with, so "Reset layout" can undo the
   * moves made since. Written by `RecordLoader` at the end of each load.
   */
  openingLayout = $state<DatasetLayout | null>(null);

  /** Reset the selection (e.g. on `clearWorkspace`). */
  reset(): void {
    this.datasetId = null;
    this.recordId = null;
    this.entities = [];
    this.entitySchemaName = null;
    this.entitySchemaFields = null;
    this.annotations = new AnnotationCollection();
    this.visibleEntityIds = null;
    this.liveDraft = null;
    this.openingLayout = null;
  }
}
