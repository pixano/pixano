/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DatasetItem, type DatasetItemType } from "../lib/types";

export async function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  let item_raw: DatasetItemType | undefined;
  let item: DatasetItem | undefined;
  const start = Date.now();
  try {
    const response = await fetch(`/dataset_items/${datasetId}/${itemId}`);

    if (response.ok) {
      item_raw = (await response.json()) as DatasetItem;
      item = new DatasetItem(item_raw);
    } else {
      item = {} as DatasetItem;
      console.log(
        "api.getDatasetItem -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    item = {} as DatasetItem;
    console.log("api.getDatasetItem -", e);
  }
  console.log("api.getDatasetItem - Done in", Date.now() - start);
  return item;
}
