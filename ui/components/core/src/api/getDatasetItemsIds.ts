/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Item } from "../lib/types";

// Request API to get all the items ids for a given dataset
export async function getDatasetItemsIds(
  datasetId: string,
  where: string | undefined = undefined,
): Promise<Array<string>> {
  const datasetItemsIds: string[] = [];
  const page_size = 1000;

  let where_qparams = "";
  if (where && where !== "") {
    where_qparams = `&where=${where}`;
  }
  for (let skip = 0; ; skip += page_size) {
    try {
      const response = await fetch(
        `/items/${datasetId}/?limit=${page_size}&skip=${skip}${where_qparams}`,
      );
      if (response.ok) {
        const res = (await response.json()) as Item[];
        datasetItemsIds.push(...res.map((item) => item.id));
        if (res && res.length < page_size) {
          break; //just to avoid 404 error log (will still appear if num items % page_size == 0)
        }
      } else {
        if (response.status != 404)
          console.log(
            "api.getDatasetItemsIds -",
            response.status,
            response.statusText,
            await response.text(),
          ); // Handle API errors
        break;
      }
    } catch (e) {
      console.log("api.getDatasetItemsIds -", e); // Handle other errors
    }
  }
  return datasetItemsIds;
}
