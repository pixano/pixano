/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import type { EntityRow } from "$lib/api/annotations.js";

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
  /** Shared annotations of the loaded record; replaced on every load. */
  annotations = $state(new AnnotationCollection());

  /** Reset the selection (e.g. on `clearWorkspace`). */
  reset(): void {
    this.datasetId = null;
    this.recordId = null;
    this.entities = [];
    this.entitySchemaName = null;
    this.annotations = new AnnotationCollection();
  }
}
