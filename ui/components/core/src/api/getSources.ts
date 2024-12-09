/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Source } from "../lib/types";

export async function getSources(datasetId: string): Promise<Source[]> {
  const sources: Source[] = [];
  const page_size = 100;
  for (let skip = 0; ; skip += page_size) {
    try {
      const response = await fetch(`/sources/${datasetId}/?limit=${page_size}&skip=${skip}`);
      if (response.ok) {
        const res = (await response.json()) as Source[];
        sources.push(...res);
        if (res && res.length < page_size) {
          break; //just to avoid 404 error log (will still appear if num items % page_size == 0)
        }
      } else {
        if (response.status != 404)
          console.log(
            "api.getSources -",
            response.status,
            response.statusText,
            await response.text(),
          ); // Handle API errors
        break;
      }
    } catch (e) {
      console.log("api.getSources -", e); // Handle other errors
    }
  }
  return sources;
}
