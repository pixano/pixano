/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Pure helpers for the set of interpolated ghosts being anchored through the
 * inspector pencil. The reactive store (`interpolatedEditingIds`) lives in
 * workspaceBaseStores; the logic sits here so it runs without the Svelte runtime.
 */

type GhostLike = {
  id: string;
  ui?: { startRef?: unknown; displayControl: { editing?: boolean } };
};

/**
 * Toggle `id` in the editing set. Enabling replaces the whole set: a single ghost is
 * anchored at a time, like a single stored annotation is edited at a time.
 */
export function toggleInterpolatedEditingId(ids: ReadonlySet<string>, id: string): Set<string> {
  return ids.has(id) ? new Set() : new Set([id]);
}

/** Return `ids` itself when `id` is absent, otherwise a copy without it. */
export function withoutInterpolatedEditingId(ids: Set<string>, id: string): Set<string> {
  if (!ids.has(id)) return ids;
  const next = new Set(ids);
  next.delete(id);
  return next;
}

/**
 * Render the interpolated ghosts (those carrying a `startRef`) whose id is in
 * `editingIds` as editable, in place. Stored annotations are left alone even when an
 * id collides.
 */
export function markInterpolatedEditing<T extends GhostLike>(
  results: T[],
  editingIds: ReadonlySet<string>,
): T[] {
  if (editingIds.size === 0) return results;
  for (const result of results) {
    if (result.ui?.startRef && editingIds.has(result.id)) {
      result.ui.displayControl.editing = true;
    }
  }
  return results;
}
