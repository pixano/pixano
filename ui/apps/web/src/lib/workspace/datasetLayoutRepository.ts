/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { parseDatasetLayout, type DatasetLayout } from "./datasetLayout.js";

/**
 * Storage seam for per-dataset layout preferences.
 *
 * The workspace depends on this interface, never on `localStorage`, so the
 * arrangement can later be moved server-side (a user-scoped preference
 * endpoint) by swapping the implementation injected into `WorkspaceManager` —
 * no call site changes. Tests inject an in-memory double for the same reason.
 */
export interface DatasetLayoutRepository {
  /** The arrangement remembered for this dataset, or `null` if there is none. */
  load(datasetId: string): DatasetLayout | null;
  /** Remember `layout` as this dataset's arrangement, replacing any previous one. */
  save(datasetId: string, layout: DatasetLayout): void;
}

/** Namespace for the per-dataset keys, so one dataset's entry never shadows another's. */
export const DATASET_LAYOUT_KEY_PREFIX = "pixano-dataset-layout:";

function storageKey(datasetId: string): string {
  return `${DATASET_LAYOUT_KEY_PREFIX}${datasetId}`;
}

/**
 * Browser-local implementation. A layout preference is a per-user comfort
 * setting, not dataset content, so it stays on the machine that set it and is
 * never worth failing a workspace over: every access is guarded because
 * `localStorage` throws outright when storage is disabled (private modes,
 * hardened browsers) or the quota is exhausted. It is also inert under SSR,
 * where `window` does not exist.
 */
export const localStorageDatasetLayoutRepository: DatasetLayoutRepository = {
  load(datasetId: string): DatasetLayout | null {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem(storageKey(datasetId));
      return raw === null ? null : parseDatasetLayout(JSON.parse(raw));
    } catch {
      // Storage blocked, or a malformed entry that JSON.parse rejected.
      return null;
    }
  },

  save(datasetId: string, layout: DatasetLayout): void {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(storageKey(datasetId), JSON.stringify(layout));
    } catch {
      // Storage blocked or full — the arrangement stays live for this session.
    }
  },
};
