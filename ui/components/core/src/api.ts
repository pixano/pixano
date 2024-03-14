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
): Promise<DatasetItems> {
  let datasetItems: DatasetItems;

  try {
    const response = await fetch(`/datasets/${datasetId}/items?page=${page}&size=${size}`);
    if (response.ok) {
      datasetItems = (await response.json()) as DatasetItems;
    } else {
      datasetItems = {} as DatasetItems;
      console.log(
        "api.getDatasetItems -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    datasetItems = {} as DatasetItems;
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

  // if (IS_DEV) {
  //   item.objects = Object.values(item.objects).reduce(
  //     (acc, obj) => {
  //       obj.datasetItemType = "video";
  //       if (obj.datasetItemType === "video" && obj.bbox) {
  //         const [x, y, w, h] = obj.bbox.coords;
  //         const box = obj.bbox;
  //         obj.displayedBox = obj.bbox; // TODO IS_DEV should be done on the frontend not api
  //         obj.track = [
  //           {
  //             start: 0,
  //             end: 10,
  //             keyBoxes: [
  //               { ...box, frameIndex: 0, coords: [x, y, w, h] },
  //               { ...box, frameIndex: 10, coords: [x + 0.1, y + 0.5, w, h] },
  //             ],
  //           },
  //           {
  //             start: 52,
  //             end: 91,
  //             keyBoxes: [
  //               { ...box, frameIndex: 52, coords: [x + 0.1, y + 0.5, w, h] },
  //               { ...box, frameIndex: 91, coords: [x, y, w, h] },
  //             ],
  //           },
  //         ];
  //       }
  //       acc[obj.id] = obj;
  //       return acc;
  //     },
  //     {} as DatasetItem["objects"],
  //   );
  // }

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
