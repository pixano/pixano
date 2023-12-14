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

import type { DatasetInfo, DatasetItems, DatasetItem } from "./lib/types/datasetTypes";

// Exports

export async function getDatasets(): Promise<Array<DatasetInfo>> {
  let datasets: Array<DatasetInfo>;

  try {
    const response = await fetch("/datasets");
    if (response.ok) {
      datasets = (await response.json()) as Array<DatasetInfo>;
    } else {
      console.log("api.getDatasets -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
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
      console.log("api.getDataset -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log("api.getDataset -", e);
  }

  return dataset;
}

export async function getDatasetItems(
  datasetId: string,
  page: number = 1,
  size: number = 100,
): Promise<DatasetItems> {
  let datasetItems: DatasetItems;

  try {
    const response = await fetch(`/datasets/${datasetId}/items?page=${page}&size=${size}`);
    if (response.ok) {
      datasetItems = (await response.json()) as DatasetItems;
    } else {
      console.log(
        "api.getDatasetItems -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getDatasetItems -", e);
  }

  return datasetItems;
}

export async function searchDatasetItems(
  datasetId: string,
  query: Record<string, string>,
  page: number = 1,
  size: number = 100,
): Promise<DatasetItems> {
  let datasetItems: DatasetItems;
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
      console.log(
        "api.searchDatasetItems -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.searchDatasetItems -", e);
  }
  return datasetItems;
}

export async function getDatasetItem(datasetId: string, itemId: string): Promise<DatasetItem> {
  let item: DatasetItem;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    if (response.ok) {
      item = (await response.json()) as DatasetItem;
    } else {
      console.log(
        "api.getDatasetItem -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getDatasetItem -", e);
  }

  return item;
}

export async function getItemEmbeddings(
  datasetId: string,
  itemId: string,
  modelId: string,
): Promise<DatasetItem> {
  let item: DatasetItem;

  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}/embeddings/${modelId}`);
    if (response.ok) {
      item = (await response.json()) as DatasetItem;
    } else {
      console.log(
        "api.getItemEmbeddings -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
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
        "api.postItemDetails -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.postItemDetails -", e);
  }
}

export async function getModels(): Promise<Array<string>> {
  let models: Array<string>;

  try {
    const response = await fetch("/models");
    if (response.ok) {
      models = (await response.json()) as Array<string>;
    } else {
      console.log("api.getModels -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log("api.getModels -", e);
  }

  return models;
}
