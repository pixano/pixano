/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { payloadBuilderFor } from "../payloadBuilders.js";
import { loadEveryKind, SEED_LOADERS, type SeedLoadContext } from "../seedLoaders.js";

/** A record with no view and no entity, whose list of `failingResource` fails. */
function contextFailing(failingResource: string): SeedLoadContext {
  return {
    datasetId: "ds",
    recordId: "rec",
    entitiesById: new Map(),
    views: new Map(),
    gateway: {
      listAnnotations: <TRow>(_datasetId: string, resource: string): Promise<TRow[]> =>
        resource === failingResource
          ? Promise.reject(new Error(`${resource} down`))
          : Promise.resolve([] as TRow[]),
    },
  };
}

describe("loadEveryKind", () => {
  // Every registered loader, so a kind added with a loader that swallows its
  // failure into an empty list fails here: a reload would take that empty list
  // for a table holding nothing, and empty the kind on screen.
  it("says which kind could not be read, and reads every other one", async () => {
    for (const failing of SEED_LOADERS) {
      const loads = await loadEveryKind(contextFailing(payloadBuilderFor(failing.kind).resource));

      const unread = loads.filter((load) => !load.read).map((load) => load.kind);
      expect(unread, `kind "${failing.kind}"`).toEqual([failing.kind]);
      expect(loads.map((load) => load.kind)).toEqual(SEED_LOADERS.map((loader) => loader.kind));
    }
  });
});
