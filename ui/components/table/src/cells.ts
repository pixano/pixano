/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import TableCell from "./TableCell.svelte";
import { type ImageFeature, type ItemFeature } from "@pixano/core";
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
    itemFeature: JSON.parse(feature.value) as ItemFeature, // 'as ItemFeature' will raise a linting error if removed,
  });

// Parse a view into an image cell
export const ImgCell = (feature) => {
  const img: ImageFeature = JSON.parse(feature.value) as ImageFeature; // 'as ImageFeature' will raise a linting error if removed
  return createRender(TableCell, {
    itemFeature: { name: img.id, dtype: img.type, value: img.thumbnail } as ItemFeature,
  });
};
