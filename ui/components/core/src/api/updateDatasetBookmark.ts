/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DatasetInfo, type DatasetInfoType } from "../lib/types";

export async function updateDatasetBookmark(
  datasetId: string,
  bookmark: string,
): Promise<DatasetInfo | null> {
  try {
    const response = await fetch(
      `/datasets/info/${datasetId}/bookmark?bookmark=${encodeURIComponent(bookmark)}`,
      { method: "PATCH" },
    );
    if (response.ok) {
      const raw = (await response.json()) as DatasetInfoType;
      return new DatasetInfo(raw);
    } else {
      console.log(
        "api.updateDatasetBookmark -",
        response.status,
        response.statusText,
        await response.text(),
      );
      return null;
    }
  } catch (e) {
    console.log("api.updateDatasetBookmark -", e);
    return null;
  }
}
