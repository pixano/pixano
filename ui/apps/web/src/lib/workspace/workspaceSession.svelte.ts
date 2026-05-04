/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
 * Lives in a `.svelte.ts` file so the runes compiler picks up `$state`.
 */
export class WorkspaceSession {
  datasetId = $state<string | null>(null);
  recordId = $state<string | null>(null);

  /** Reset the selection (e.g. on `clearWorkspace`). */
  reset(): void {
    this.datasetId = null;
    this.recordId = null;
  }
}
