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
      console.log(response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log(e);
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
      console.log(response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log(e);
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
      console.log(response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log(e);
  }

  return datasetStats;
}

export async function getItemDetails(datasetId: String, itemId: Number) {
  let itemDetails = null;
  try {
    const response = await fetch(`/datasets/${datasetId}/items/${itemId}`);
    if (response.ok) {
      itemDetails = await response.json();
    } else {
      console.log(response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log(e);
  }

  return itemDetails;
}
