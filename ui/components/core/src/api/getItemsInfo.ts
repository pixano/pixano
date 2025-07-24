/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetMoreInfo } from "../lib/types/dataset/DatasetMoreInfo";
import { splitWithLimit } from "../utils";

export async function getItemsInfo(
  datasetId: string,
  item_ids: string[] | null = null,
  options?: { signal?: AbortSignal },
): Promise<Array<DatasetMoreInfo>> {
  let infos: Array<DatasetMoreInfo>;

  try {
    let url: string;

    if (item_ids && item_ids.length > 0) {
      const ids_chunks = splitWithLimit(item_ids, "&ids=", 8000);
      //we assume every ids goes in first chunk as a page has 20 items (could be increased but should be OK)
      //if one day the page size is really increased,
      //then we should map through chunks like in "deleteSchemaByIds.ts"
      url = `/items_info/${datasetId}?ids=${ids_chunks[0]}`;
    } else url = `/items_info/${datasetId}`;
    const response = await fetch(url, {
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
