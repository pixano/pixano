/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ViewEmbedding } from "../lib/types";

export async function getViewEmbeddings(
  datasetId: string,
  itemId: string,
  tableName: string,
): Promise<Array<ViewEmbedding>> {
  let viewEmbeddings: Array<ViewEmbedding> | undefined;

  try {
    const response = await fetch(`/embeddings/${datasetId}/${tableName}/?item_ids=${itemId}`);
    if (response.ok) {
      viewEmbeddings = (await response.json()) as Array<ViewEmbedding>;
    } else {
      viewEmbeddings = [];
      console.log(
        "api.getViewEmbeddings -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    viewEmbeddings = [];
    console.log("api.getViewEmbeddings -", e);
  }
  return viewEmbeddings;
}
