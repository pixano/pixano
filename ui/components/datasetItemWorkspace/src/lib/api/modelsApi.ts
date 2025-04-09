/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";
import { get } from "svelte/store";

import type { DatasetInfo } from "@pixano/core";
import { WorkspaceType } from "@pixano/core";
import { api } from "@pixano/core/src";

import { currentDatasetStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
import { embeddings, mediaViews, modelsUiStore } from "../../lib/stores/datasetItemWorkspaceStores";
import { currentFrameIndex } from "../../lib/stores/videoViewerStores";

export function loadViewEmbeddings(forceLoad: boolean = false) {
  const dataset = get(currentDatasetStore);
  const models = get(modelsUiStore);
  if (
    (forceLoad || models.yetToLoadEmbedding) &&
    models.selectedModelName !== "" &&
    models.selectedTableName !== ""
  ) {
    let itemId: string = "";
    const mView = get(mediaViews);
    const currentFIndex = get(currentFrameIndex);
    modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: false }));
    const viewIdsSet = new Set<string>();
    for (const view in mView) {
      if (Array.isArray(mView[view])) {
        const currentView = mView[view].find((sf) => sf.data.frame_index === currentFIndex);
        if (currentView) {
          viewIdsSet.add(currentView.id);
          itemId = currentView.data.item_ref.id; //same across all views so OK to overwrite
        }
      } else {
        itemId = mView[view].data.item_ref.id;
      }
    }
    let where: string = "";
    if (dataset.workspace === WorkspaceType.VIDEO) {
      if (viewIdsSet.size === 1) {
        where = `view_ref.id = '${viewIdsSet.values().next().value}'`;
      } else if (viewIdsSet.size > 1) {
        where = `view_ref.id IN ('${Array.from(viewIdsSet).join("', '")}')`;
      }
    }

    fetchViewEmbeddings(itemId, models.selectedTableName, dataset.id, where)
      .then((results) => {
        embeddings.set(results);
        modelsUiStore.update((store) => ({
          ...store,
          currentModalOpen: "none",
        }));
      })
      .catch((err) => {
        modelsUiStore.update((store) => ({
          ...store,
          selectedTableName: "",
          currentModalOpen: "noEmbeddings",
        }));
        console.error("cannot load Embeddings", err);
        embeddings.set({});
      });
  }
}

async function fetchViewEmbeddings(
  itemId: string,
  selectedTableName: string,
  datasetId: DatasetInfo["id"],
  where: string,
): Promise<Record<string, ort.Tensor>> {
  const embeddings: Record<string, ort.Tensor> = {};
  if (selectedTableName) {
    const view_embeddings = await api.getViewEmbeddings(
      datasetId,
      itemId,
      selectedTableName,
      where,
    );
    if (view_embeddings.length > 0) {
      for (const view_embedding of view_embeddings) {
        try {
          let shape = view_embedding.data.shape;
          if (shape.length === 3) {
            shape = [1, shape[0], shape[1], shape[2]];
          }
          embeddings[view_embedding.data["view_ref"].id] = new ort.Tensor(
            "float32",
            view_embedding.data.vector,
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
