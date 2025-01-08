/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { DatasetInfo, type DatasetInfoType } from "../lib/types";

export async function getDatasetsInfo(): Promise<Array<DatasetInfo>> {
  let datasets_raw: Array<DatasetInfoType>;
  let datasets: Array<DatasetInfo>;

  try {
    const response = await fetch("/datasets/info");
    if (response.ok) {
      datasets_raw = (await response.json()) as Array<DatasetInfoType>;
      datasets = datasets_raw.map((ds_raw) => {
        return new DatasetInfo(ds_raw);
      });
    } else {
      datasets = [];
      console.log(
        "api.getDatasetsInfo -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    datasets = [];
    console.log("api.getDatasetsInfo -", e);
  }

  return datasets;
}
