/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetMoreInfo } from "../lib/types/dataset/DatasetMoreInfo";

export async function getItemsInfo(
  datasetId: string,
  options?: { signal?: AbortSignal },
): Promise<Array<DatasetMoreInfo>> {
  let infos: Array<DatasetMoreInfo>;

  try {
    const response = await fetch(`/items_info/${datasetId}/`, {
      method: "GET",
      signal: options?.signal,
    });
    if (response.ok) {
      infos = (await response.json()) as Array<DatasetMoreInfo>;
    } else {
      infos = [];
      console.log(
        "api.getItemsInfo -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    infos = [];
    if (!(typeof e === "string" && e === "aborted")) console.log("api.getItemsInfo -", e);
  }

  return infos;
}
