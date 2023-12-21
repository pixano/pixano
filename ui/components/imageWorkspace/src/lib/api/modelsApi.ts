import * as ort from "onnxruntime-web";

import type { DatasetItem, DatasetInfo } from "@pixano/core";
import { api } from "@pixano/core";
import { npy } from "@pixano/models";

export async function loadEmbeddings(
  selectedItem: DatasetItem,
  selectedModelName: string,
  selectedDataset: DatasetInfo,
): Promise<Record<string, ort.Tensor>> {
  const embeddings: Record<string, ort.Tensor> = {};
  if (selectedModelName) {
    const item = await api.getItemEmbeddings(
      selectedDataset.id,
      selectedItem.id,
      selectedModelName,
    );
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
