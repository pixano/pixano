/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetLayout } from "../datasetLayout.js";
import type { DatasetLayoutRepository } from "../datasetLayoutRepository.js";

/**
 * In-memory `DatasetLayoutRepository` for tests: same contract as the
 * localStorage one, but with per-instance state so suites never leak stored
 * arrangements into each other, and a `saved` log so a test can assert *what*
 * was written rather than only that something was.
 */
export interface FakeDatasetLayoutRepository extends DatasetLayoutRepository {
  /** Every `save` call, in order. */
  saved: Array<{ datasetId: string; layout: DatasetLayout }>;
}

export function makeLayoutRepository(
  initial: Record<string, DatasetLayout> = {},
): FakeDatasetLayoutRepository {
  const store = new Map(Object.entries(initial));
  const saved: FakeDatasetLayoutRepository["saved"] = [];

  return {
    saved,
    load: (datasetId) => store.get(datasetId) ?? null,
    save: (datasetId, layout) => {
      store.set(datasetId, layout);
      saved.push({ datasetId, layout });
    },
  };
}
