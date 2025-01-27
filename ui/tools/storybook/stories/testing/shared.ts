/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { FeaturesValues, ImageDatasetItem, ItemView } from "@pixano/core/src";
import fleurs from "../../assets/fleurs.jpg";
import tiff from "../../assets/tiff.png";
import { imgThumbnail } from "../assets/base64image";

// IMPORT ALL IMAGES
export const gallery: string[] = Object.values(
  import.meta.glob("../../assets/videos/mock/*.{png,jpg,jpeg,PNG,JPEG,tif}", {
    eager: true,
    as: "url",
  }),
);

export const mockImage: ItemView = {
  id: "image",
  type: "image",
  uri: fleurs.slice(1),
  thumbnail: imgThumbnail,
  frame_number: undefined,
  total_frames: undefined,
  features: {
    width: {
      name: "width",
      dtype: "int",
      value: 770,
    },
    height: {
      name: "height",
      dtype: "int",
      value: 513,
    },
  },
};

export const mock16BitImage: ItemView = {
  id: "image",
  type: "image",
  uri: tiff.slice(1),
  thumbnail: "img",
  frame_number: undefined,
  total_frames: undefined,
  features: {
    width: {
      name: "width",
      dtype: "int",
      value: 770,
    },
    height: {
      name: "height",
      dtype: "int",
      value: 513,
    },
  },
};
export const mock16BitImageDatasetItem: ImageDatasetItem = {
  type: "image",
  id: "fleurs.jpg",
  split: "demo",
  datasetId: "foo",
  features: {
    label: {
      name: "label",
      dtype: "str",
      value: "printemps",
    },
    category_name: {
      name: "category_name",
      dtype: "str",
      value: "foo",
    },
  },
  views: {
    image: mock16BitImage,
  },
  objects: [],
  embeddings: {},
};

export const mockFeaturesValues: FeaturesValues = {
  main: {
    label: {
      restricted: false,
      values: ["arbre", "oranges", "poire", "None", "abeille", "printemps"],
    },
    category_name: { restricted: false, values: ["foo", "None"] },
  },
  objects: {
    category_id: { restricted: false, values: [] },
    category_name: {
      restricted: false,
      values: [
        "toilet",
        "chair",
        "oranges",
        "donut",
        "bar",
        "apple",
        "dining table",
        "pizza",
        "refrigerator",
        "None",
        "potted plant",
        "orange",
        "bird",
        "cake",
        "sheep",
        "salade",
        "broccoli",
        "olive",
        "sandwich",
        "oooo",
        "banano",
        "carrot",
        "bowl",
        "banana",
        "carrotes",
        "foo",
        "choubidou",
        "bottle",
      ],
    },
    category: { restricted: false, values: ["vzfe", "front", "None", "seed", "foo", "bar"] },
  },
};
