/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import * as api from "$lib/api";
import { mapFeatureValues } from "$lib/utils/itemLoadUtils";
import { buildWorkspaceManifest, getWorkspaceResourcePaths } from "$lib/workspace/manifest";

export const load: PageLoad = async ({ params, parent }) => {
  const { dataset, schema, featureValues: rawFeatureValues } = await parent();
  const workspaceManifest = buildWorkspaceManifest(schema, dataset.workspace);
  const workspaceResources = getWorkspaceResourcePaths(workspaceManifest, "annotations");

  const { workspaceData } = await api.loadWorkspaceRecord(
    dataset.id,
    encodeURIComponent(params.itemId),
    dataset.workspace,
    workspaceResources,
  );
  const featureValues = mapFeatureValues(rawFeatureValues, schema);

  return { workspaceData, featureValues, workspaceManifest };
};
