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

import type { Dataset, DatasetItems, ItemDetails, Dict } from "./interfaces";

// Exports

export async function getDatasetList(): Promise<Array<Dataset>> {
  let datasets: Array<Dataset>;

  try {
    const response = await fetch("/datasets");
    if (response.ok) {
      datasets = await response.json();
    } else {
      console.log(
        "api.getDatasetList -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getDatasetList -", e);
  }

  return datasets;
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
      datasetItems = await response.json();
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

export async function getDatasetStats(datasetId: string): Promise<Array<object>> {
  let datasetStats: Array<object>;

  try {
    const response = await fetch(`/datasets/${datasetId}/stats`);
    if (response.ok) {
      datasetStats = await response.json();
    } else {
      console.log(
        "api.getDatasetStats -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getDatasetStats -", e);
  }

  return datasetStats;
}

export async function getItemDetails(datasetId: string, itemId: string): Promise<ItemDetails> {
  let itemDetails: ItemDetails;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    if (response.ok) {
      itemDetails = await response.json();
    } else {
      console.log(
        "api.getItemDetails -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getItemDetails -", e);
  }

  return itemDetails;
}

export async function getItemEmbeddings(datasetId: string, itemId: string): Promise<Dict<string>> {
  let embeddings: Dict<string>;

  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}/embeddings`);
    if (response.ok) {
      embeddings = await response.json();
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
  return embeddings;
}

export async function postItemDetails(itemDetails: object, datasetId: string, itemId: string) {
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}/details`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(itemDetails),
      method: "POST",
    });
    if (!response.ok) {
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

export async function getSearchResult(
  datasetId: string,
  query: string,
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
      body: JSON.stringify({ query: query }),
      method: "POST",
    });
    if (response.ok) {
      datasetItems = await response.json();
    } else {
      console.log(
        "api.getSearchResult -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.getSearchResult -", e);
  }
  return datasetItems;
}
