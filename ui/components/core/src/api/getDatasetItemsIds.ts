/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Request API to get all the items ids for a given dataset
export async function getDatasetItemsIds(datasetId: string): Promise<Array<string>> {
  let datasetItemsIds: string[] = [];

  try {
    const response = await fetch(`/browser/item_ids/${datasetId}`);
    if (response.ok) {
      datasetItemsIds = (await response.json()) as string[];
    } else {
      if (response.status != 404)
        console.log(
          "api.getDatasetItemsIds -",
          response.status,
          response.statusText,
          await response.text(),
        ); // Handle API errors
    }
  } catch (e) {
    console.log("api.getDatasetItemsIds -", e); // Handle other errors
  }
  return datasetItemsIds;
}
