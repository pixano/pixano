import * as ort from "onnxruntime-web";

import type { DatasetItem, DatasetInfo } from "@pixano/core";
import { api } from "@pixano/core/src";
import { npy } from "@pixano/models/src";

export async function loadEmbeddings(
  itemId: DatasetItem["id"],
  selectedModelName: string,
  datasetId: DatasetInfo["id"],
): Promise<Record<string, ort.Tensor>> {
  const embeddings: Record<string, ort.Tensor> = {};
  if (selectedModelName) {
    const item = await api.getItemEmbeddings(datasetId, itemId, selectedModelName);
    if (item) {
      for (const [viewId, viewEmbeddingBytes] of Object.entries(item.embeddings)) {
        try {
          const viewEmbeddingArray = npy.parse(npy.b64ToBuffer(viewEmbeddingBytes.data));
          embeddings[viewId] = new ort.Tensor(
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
  return embeddings;
}
