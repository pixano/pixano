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
import TableCell from "./TableCell.svelte";
import type { ItemView, ItemFeature } from "@pixano/core";
import { createRender } from "svelte-headless-table";

// Default cells that we assume are present in every dataset
export const DefaultCell = (feature: { id: string; value: string | number }) => {
  if (feature.id === "id") {
    return createRender(TableCell, {
      itemFeature: { name: feature.id, dtype: "int", value: feature.value },
    });
  } else if (feature.id === "split")
    return createRender(TableCell, {
      itemFeature: { name: feature.id, dtype: "str", value: feature.value },
    });
};

// Parse a feature into a table cell
export const FeatureCell = (feature) =>
  createRender(TableCell, {
    itemFeature: JSON.parse(feature.value) as ItemFeature, // 'as ItemFeature' will provoc a linting error if removed,
  });

// Parse a view into an image cell
export const ImgCell = (feature) => {
  const img: ItemView = JSON.parse(feature.value) as ItemView; // 'as ItemView' will provoc a linting error if removed
  return createRender(TableCell, {
    itemFeature: { name: img.id, dtype: img.type, value: img.thumbnail },
  });
};
