/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";

import type { DatasetInfo } from "@pixano/core";
import { api } from "@pixano/core/src";

export async function loadViewEmbeddings(
  itemId: string,
  selectedTableName: string,
  datasetId: DatasetInfo["id"],
): Promise<Record<string, ort.Tensor>> {
  const embeddings: Record<string, ort.Tensor> = {};
  if (selectedTableName) {
    const view_embeddings = await api.getViewEmbeddings(datasetId, itemId, selectedTableName);
    if (view_embeddings.length > 0) {
      for (const view_embedding of view_embeddings) {
        try {
          let shape = view_embedding.data.vector.shape;
          if (shape.length === 3) {
            shape = [1, shape[0], shape[1], shape[2]];
          }
          embeddings[view_embedding.data["view_ref"].name] = new ort.Tensor(
            "float32",
            view_embedding.data.vector.values,
            shape,
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
