/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Source } from "../lib/types";

export async function getSources(datasetId: string): Promise<Source[]> {
  const response = await fetch(`/sources/${datasetId}`);
  if (response.ok) {
    return (await response.json()) as Source[];
  } else {
    if (response.status != 404)
      console.log("api.getSources -", response.status, response.statusText, await response.text()); // Handle API errors
  }
  return [];
}
