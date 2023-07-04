/**
@copyright CEA-LIST/DIASI/SIALV/LVA (2023)
@author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
@license CECILL-C

This software is a collaborative computer program whose purpose is to
generate and explore labeled data for computer vision applications.
This software is governed by the CeCILL-C license under French law and
abiding by the rules of distribution of free software. You can use, 
modify and/ or redistribute the software under the terms of the CeCILL-C
license as circulated by CEA, CNRS and INRIA at the following URL

http://www.cecill.info
*/

// Exports
/**
 * Get the list of all datasets in the library
 * @returns
 */
export async function getDatasetsList() {
  let datasets = null;

  try {
    const response = await fetch("/datasets");

    datasets = await response.json();
  } catch (e) {
    console.log(e);
  }

  return datasets;
}

/**
 * Get dataset items
 * @param datasetId
 * @returns
 */
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
    if (!response.ok) {
      //TODO: error cases other than 404 ?
      console.log("No dataset content at page", page);
      return null;
    }
    datasetItems = await response.json();
  } catch (e) {
    console.log(e);
  }

  return datasetItems;
}

/**
 * Get dataset items
 * @param datasetId
 * @returns
 */
export async function getDatasetStats(datasetId: String) {
  let datasetStats = null;

  try {
    const response = await fetch(`/datasets/${datasetId}/stats`);
    if (!response.ok) {
      //TODO: error cases other than 404 ?
      console.log("No stats");
      return [];
    }
    datasetStats = await response.json();
  } catch (e) {
    console.log(e);
  }

  return datasetStats;
}

export async function getItemDetails(datasetId: String, itemId: Number) {
  let features = null;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    features = await response.json();
  } catch (e) {
    console.log(e);
  }

  return features;
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
        "WARNING",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("ERROR getting Embeddings", e);
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
    if (response.ok) {
      console.log("Annotations sent OK");
    } else {
      console.log(
        "WARNING",
        response.status,
        response.statusText,
        await response.text()
      );
    }
  } catch (e) {
    console.log("ERROR posting annotations", e);
  }
}

export async function getModel() {}
