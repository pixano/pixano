/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SplitStatusCount } from "../lib/types";

export async function getDatasetSplits(
  datasetId: string,
): Promise<SplitStatusCount[]> {
  try {
    const response = await fetch(`/datasets/info/${datasetId}/splits`);
    if (response.ok) {
      return (await response.json()) as SplitStatusCount[];
    } else {
      console.log(
        "api.getDatasetSplits -",
        response.status,
        response.statusText,
        await response.text(),
      );
      return [];
    }
  } catch (e) {
    console.log("api.getDatasetSplits -", e);
    return [];
  }
}
