/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Dataset } from "../lib/types";

export async function getDataset(datasetId: string): Promise<Dataset> {
  let dataset;

  try {
    const response = await fetch(`/datasets/${datasetId}`);
    if (response.ok) {
      dataset = (await response.json()) as Dataset;
    } else {
      dataset = {} as Dataset;
      console.log("api.getDataset -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    dataset = {} as Dataset;
    console.log("api.getDataset -", e);
  }
  return dataset;
}
