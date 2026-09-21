/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Storage seam for the colour mode a user last chose on a dataset.
 *
 * Per **dataset**, not per widget: a widget's storage is rebuilt by
 * `addStorage()` on every record load, so a choice kept there survives exactly
 * until the next record — which is the moment it matters most, since stepping
 * through a sequence is how a point cloud is actually reviewed. Same reasoning
 * and same shape as `DatasetLayoutRepository`: every record of a dataset has
 * the same sensors, so a preference set on one is the right default for the
 * others.
 *
 * An interface rather than a direct `localStorage` call so the preference can
 * later move server-side by swapping the implementation, and so tests inject a
 * double instead of leaning on browser storage.
 */
export interface ColorModePreferenceRepository {
  /** The mode id remembered for this dataset, or null if none was ever chosen. */
  load(datasetId: string): string | null;
  /** Remember `modeId` as this dataset's colour mode, replacing any previous one. */
  save(datasetId: string, modeId: string): void;
}

/** Namespace for the per-dataset keys, so one dataset never shadows another. */
export const COLOR_MODE_KEY_PREFIX = "pixano-point-cloud-color-mode:";

function storageKey(datasetId: string): string {
  return `${COLOR_MODE_KEY_PREFIX}${datasetId}`;
}

/**
 * Browser-local implementation. A colour mode is a per-user viewing preference
 * rather than dataset content, so it stays on the machine that set it and is
 * never worth failing a workspace over: every access is guarded because
 * `localStorage` throws outright when storage is disabled (private modes,
 * hardened browsers) or the quota is exhausted, and is absent under SSR.
 *
 * No validation of the stored value beyond "non-empty string": `colorModeFor`
 * already resolves an unknown id to the default, so an id left behind by a
 * removed mode degrades on read rather than needing a migration here.
 */
export const localStorageColorModePreferenceRepository: ColorModePreferenceRepository = {
  load(datasetId: string): string | null {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem(storageKey(datasetId));
      return raw !== null && raw.length > 0 ? raw : null;
    } catch {
      return null;
    }
  },

  save(datasetId: string, modeId: string): void {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(storageKey(datasetId), modeId);
    } catch {
      // Storage blocked or full — the choice stays live for this session.
    }
  },
};
