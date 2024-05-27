/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Imports
import type {
  DatasetInfo,
  DatasetItems,
  DatasetItem,
  ExplorerData,
  VideoObject,
} from "./lib/types/datasetTypes";

// Exports
export async function getDatasets(): Promise<Array<DatasetInfo>> {
  let datasets: Array<DatasetInfo>;

  try {
    const response = await fetch("/datasets");
    if (response.ok) {
      datasets = (await response.json()) as Array<DatasetInfo>;
    } else {
      datasets = [];
      console.log("api.getDatasets -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    datasets = [];
    console.log("api.getDatasets -", e);
  }

  return datasets;
}

export async function getDataset(datasetId: string): Promise<DatasetInfo> {
  let dataset: DatasetInfo;

  try {
    const response = await fetch(`/datasets/${datasetId}`);
    if (response.ok) {
      dataset = (await response.json()) as DatasetInfo;
    } else {
      dataset = {} as DatasetInfo;
      console.log("api.getDataset -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    dataset = {} as DatasetInfo;
    console.log("api.getDataset -", e);
  }

  return dataset;
}

export async function getDatasetItems(
  datasetId: string,
  page: number = 1,
  size: number = 100,
): Promise<ExplorerData> {
  let datasetItems: ExplorerData;

  try {
    const response = await fetch(`/datasets/${datasetId}/explorer?page=${page}&size=${size}`);
    if (response.ok) {
      datasetItems = (await response.json()) as ExplorerData;
    } else {
      datasetItems = {} as ExplorerData;
      console.log(
        "api.getDatasetItems -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    datasetItems = {} as ExplorerData;
    console.log("api.getDatasetItems -", e);
  }

  return datasetItems;
}

// Request API to get all the items ids for a given dataset
export async function getDatasetItemsIds(datasetId: string): Promise<Array<string>> {
  let datasetItemsIds: string[] = [];

  try {
    const response = await fetch(`/datasets/${datasetId}/item_ids`);
    if (response.ok)
      datasetItemsIds = (await response.json()) as string[]; // Parse API response if valid
    else
      console.log("api.getDataset -", response.status, response.statusText, await response.text()); // Handle API errors
  } catch (e) {
    console.log("api.getDataset -", e); // Handle other errors
  }

  return datasetItemsIds;
}

export async function searchDatasetItems(
  datasetId: string,
  query: Record<string, string>,
  page: number = 1,
  size: number = 100,
): Promise<DatasetItems> {
  let datasetItems: DatasetItems | undefined;
  try {
    const response = await fetch(`/datasets/${datasetId}/search?page=${page}&size=${size}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(query),
      method: "POST",
    });
    if (response.ok) {
      datasetItems = (await response.json()) as DatasetItems;
    } else {
      throw new Error("api.searchDatasetItems");
    }
  } catch (e) {
    throw new Error("api.searchDatasetItems");
  }
  return datasetItems;
}

export async function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  let item: DatasetItem | undefined;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    if (response.ok) {
      item = (await response.json()) as DatasetItem;
      // TODO : remove this when the backend is fixed
      // TODO : API changes | keyBoxes should be renamed `boxes` since is_key is now a params
      if (item.type === "video") {
        const objects: Array<VideoObject> = item.objects.map((obj) => {
          obj.track = obj.track.map((tracklet) => {
            tracklet.start = tracklet.keyBoxes[0].frame_index;
            tracklet.end = tracklet.keyBoxes[tracklet.keyBoxes.length - 1].frame_index;
            tracklet.keyBoxes = tracklet.keyBoxes.map((keyBox) => {
              if (
                keyBox.frame_index === tracklet.keyBoxes[0].frame_index ||
                keyBox.frame_index === tracklet.keyBoxes[tracklet.keyBoxes.length - 1].frame_index
              ) {
                keyBox.is_key = true;
              }
              return keyBox;
            });
            return tracklet;
          });
          obj.displayedBox = undefined;
          return obj;
        });
        item.objects = objects;
      }
    } else {
      item = {} as DatasetItem;
      console.log(
        "api.getDatasetItem -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    item = {} as DatasetItem;
    console.log("api.getDatasetItem -", e);
  }

  return item;
}

export async function getItemEmbeddings(
  datasetId: string,
  itemId: string,
  modelId: string,
): Promise<DatasetItem> {
  let item: DatasetItem | undefined;

  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}/embeddings/${modelId}`);
    if (response.ok) {
      item = (await response.json()) as DatasetItem;
    } else {
      item = {} as DatasetItem;
      console.log(
        "api.getItemEmbeddings -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    item = {} as DatasetItem;
    console.log("api.getItemEmbeddings -", e);
  }
  return item;
}

export async function postDatasetItem(datasetId: string, item: DatasetItem) {
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${item.id}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(item),
      method: "POST",
    });
    if (response.ok) {
      console.log(
        "api.postDatasetItem -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.postDatasetItem -", e);
  }
}

export async function getModels(): Promise<Array<string>> {
  let models: Array<string> | undefined;

  try {
    const response = await fetch("/models");
    if (response.ok) {
      models = (await response.json()) as Array<string>;
    } else {
      models = [];
      console.log("api.getModels -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    models = [];
    console.log("api.getModels -", e);
  }

  return models;
}
