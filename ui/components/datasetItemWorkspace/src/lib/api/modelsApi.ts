/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";

import type { DatasetInfo } from "@pixano/core";
import { api } from "@pixano/core/src";
import { npy } from "@pixano/models/src";

//TODO SAM is deactivated for now, and currently not compatible with data model
export async function loadEmbeddings(
  itemId: string,
  selectedModelName: string,
  datasetId: DatasetInfo["id"],
): Promise<Record<string, ort.Tensor>> {
  const embeddings: Record<string, ort.Tensor> = {};
  if (selectedModelName) {
    const item = await api.getItemEmbeddings(datasetId, itemId, selectedModelName);
    // @ts-expect-error DataModel is not yet able to handle embeddings, need rework
    if (item.embeddings) {
      // @ts-expect-error DataModel is not yet able to handle embeddings, need rework
      for (const [view_name, viewEmbeddingBytes] of Object.entries(item.embeddings)) {
        try {
          // @ts-expect-error DataModel is not yet able to handle embeddings, need rework
          const viewEmbeddingArray = npy.parse(npy.b64ToBuffer(viewEmbeddingBytes.data));
          embeddings[view_name] = new ort.Tensor(
            "float32",
            viewEmbeddingArray.data,
            viewEmbeddingArray.shape,
          );
        } catch (e) {
          console.warn("AnnotationWorkspace.loadModel - Error loading embeddings", e);
        }
      }
    }
  }
  if (Object.keys(embeddings).length === 0) {
    throw new Error("No embeddings found");
  }
  return embeddings;
}
