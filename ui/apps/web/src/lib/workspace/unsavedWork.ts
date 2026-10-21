/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ResourceMutation } from "$lib/annotations/types.js";

/** Everything of the open record that is not stored yet, as the workspace holds it. */
export interface UnsavedWorkSources {
  /** The changes not stored yet: those queued, and the one on the wire. */
  readonly changes: readonly Pick<ResourceMutation, "localAnnotationId">[];
  /** The record's annotations; a draft (`persisted` false) has no row in the dataset yet. */
  readonly annotations: readonly { readonly id: string; readonly persisted: boolean }[];
  /** Whether the entity form is open — for a draft's entity, or for a reassignment. */
  readonly entityChoiceOpen: boolean;
  /** How many holders of staged work have their flag raised (`WorkspaceSession.stagedWork`). */
  readonly stagedHolders: number;
}

/**
 * How many items of the open record are unsaved — the one number every unsaved
 * counter shows, and the one `flushSave` reads: the record is all saved only
 * when it is zero.
 *
 * - **An annotation counts once**, whatever it holds: an edit, a new entity
 *   and the update naming it, a draft not stored yet.
 * - **A change that names no annotation** counts on its own.
 * - **An open entity form** counts once. A draft's form is its draft, already
 *   counted: a draft the queue holds no change for is one whose entity is still
 *   being chosen, its create queued only once the choice is made. Otherwise the
 *   form is a stored annotation's reassignment, which nothing else counts.
 * - **Each raised holder of staged work** counts once: what it holds — points
 *   before Enter, a box being resized — is in no change yet, and may concern an
 *   annotation already counted for another one.
 */
export function countUnsavedWork(sources: UnsavedWorkSources): number {
  const items = new Set<unknown>();
  for (const change of sources.changes) items.add(change.localAnnotationId ?? change);
  let draftAwaitsEntity = false;
  for (const annotation of sources.annotations) {
    if (annotation.persisted || items.has(annotation.id)) continue;
    draftAwaitsEntity = true;
    items.add(annotation.id);
  }
  const reassignmentOpen = sources.entityChoiceOpen && !draftAwaitsEntity;
  return items.size + (reassignmentOpen ? 1 : 0) + sources.stagedHolders;
}
