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

// Exports

export async function getDatasetsList() {
  let datasets = null;

  try {
    const response = await fetch("/datasets");
    if (response.ok) {
      datasets = await response.json();
    } else {
      console.log(
        "api.getDatasetsList -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.getDatasetsList -", e);
  }

  return datasets;
}

export async function getDatasetItems(
  datasetId: String,
  page: number = 1,
  size: number = 100
) {
  let datasetItems = null;

  try {
    const response = await fetch(
      `/datasets/${datasetId}/items?page=${page}&size=${size}`
    );
    if (response.ok) {
      datasetItems = await response.json();
    } else {
      console.log(
        "api.getDatasetItems -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.getDatasetItems -", e);
  }

  return datasetItems;
}

export async function getDatasetStats(datasetId: String) {
  let datasetStats = null;

  try {
    const response = await fetch(`/datasets/${datasetId}/stats`);
    if (response.ok) {
      datasetStats = await response.json();
    } else {
      console.log(
        "api.getDatasetStats -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.getDatasetStats -", e);
  }

  return datasetStats;
}

export async function getItemDetails(datasetId: String, itemId: string) {
  let itemDetails = null;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    if (response.ok) {
      itemDetails = await response.json();
    } else {
      console.log(
        "api.getItemDetails -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.getItemDetails -", e);
  }

  return itemDetails;
}

export async function getViewEmbedding(
  datasetId: String,
  itemId: string,
  viewId: string = "image"
) {
  let embedding = null;

  try {
    const response = await fetch(
      `/datasets/${datasetId}/items/${itemId}/${viewId}/embedding`,
      {
        headers: {
          Accept: "application/octet-stream",
          "Content-Type": "application/octet-stream",
        },
        method: "POST",
      }
    );
    if (response.ok) {
      embedding = await response.arrayBuffer();
    } else {
      console.log(
        "api.getViewEmbedding -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.getViewEmbedding -", e);
  }
  return embedding;
}

export async function postAnnotations(
  anns: any,
  datasetId: String,
  itemId: string
) {
  try {
    const response = await fetch(
      `/datasets/${datasetId}/items/${itemId}/annotations`,
      {
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(anns),
        method: "POST",
      }
    );
    if (!response.ok) {
      console.log(
        "api.postAnnotations -",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("api.postAnnotations -", e);
  }
}
