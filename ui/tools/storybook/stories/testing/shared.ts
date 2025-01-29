/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationType, EntityType, FeaturesValues, ImageType, ViewType } from "@pixano/core";
import { BaseSchema, Image } from "@pixano/core";
import fleurs from "../../assets/fleurs.jpg";
import tiff from "../../assets/tiff.png";

// IMPORT ALL IMAGES
export const gallery: string[] = Object.values(
  import.meta.glob("../../assets/videos/mock/*.{png,jpg,jpeg,PNG,JPEG,tif}", {
    eager: true,
    as: "url",
  }),
);

const baseAnnotationType = {
  item_ref: {
    id: "fleurs.jpg",
    name: "fleurs.jpg",
  },
  view_ref: {
    id: "view_id",
    name: "view_name",
  },
  source_ref: {
    id: "Ground Truth",
    name: "Ground Truth",
  },
};
export const mockAnnotationType: AnnotationType = {
  ...baseAnnotationType,
  entity_ref: {
    id: "entity_id",
    name: "entity_name",
  },
};

export const mockMessageType: AnnotationType = {
  ...baseAnnotationType,
  entity_ref: {
    id: "conversation_id",
    name: "conversation_name",
  },
};

export const mockEntityType: EntityType = {
  item_ref: {
    id: "fleurs.jpg",
    name: "fleurs.jpg",
  },
  view_ref: {
    id: "image",
    name: "image",
  },
  parent_ref: {
    id: "",
    name: "",
  },
};

export const mockViewType: ViewType = {
  item_ref: {
    id: "fleurs.jpg",
    name: "fleurs.jpg",
  },
  parent_ref: {
    id: "",
    name: "",
  },
};

const baseImageData = {
  width: 770,
  height: 513,
  format: "jpg",
};

const imageData: ImageType = {
  ...baseImageData,
  url: (fleurs as string).slice(1),
};

export const mockImage = new Image({
  id: "image_id",
  table_info: { name: "image", group: "view", base_schema: BaseSchema.Image },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: { ...imageData, ...mockViewType },
});

const sixteenBitsImageData: ImageType = {
  ...baseImageData,
  url: (tiff as string).slice(1),
};
export const mock16BitImage = new Image({
  id: "image_id",
  table_info: { name: "image", group: "view", base_schema: BaseSchema.Image },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  data: { ...sixteenBitsImageData, ...mockViewType },
});

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
