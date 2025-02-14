/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Tracklet, VideoDatasetItem, VideoItemBBox } from "@pixano/core";

import { gallery, mockImage } from "../shared";

const displayedMBox: VideoItemBBox[] = [
  {
    coords: [0.5362540535588254, 0.1909159114200253, 0.09993766916635072, 0.18671048750633337],
    view_id: "image",
    format: "xywh",
    is_normalized: true,
    confidence: 1,
    frame_index: 0,
    tracklet_id: "trackletId",
  },
];

const track: Tracklet[] = [
  {
    start: 0,
    end: 73,
    id: "trackletId",
  },
];

export const mockVideoDatasetItem: VideoDatasetItem = {
  id: "fleurs.jpg",
  type: "video",
  split: "demo",
  datasetId: "",
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
    image: gallery.map((image) => ({
      ...mockImage,
      features: {
        width: {
          name: "width",
          dtype: "int",
          value: 600,
        },
        height: {
          name: "height",
          dtype: "int",
          value: 338,
        },
      },
      // remove first caracter of image
      uri: image.slice(1),
    })),
  },
  objects: [
    {
      id: "EZ4s6R0E_y",
      datasetItemType: "video",
      boxes: [
        {
          coords: [
            0.5362540535588254, 0.1909159114200253, 0.09993766916635072, 0.18671048750633337,
          ],
          format: "xywh",
          is_normalized: true,
          confidence: 1,
          frame_index: 0,
          is_key: true,
          is_thumbnail: true,
          tracklet_id: "trackletId",
          view_id: "image",
        },
        {
          coords: [
            0.5914342337390056, 0.2693339921343171, 0.09993766916635072, 0.18671048750633337,
          ],
          format: "xywh",
          is_normalized: true,
          confidence: 1,
          frame_index: 73,
          is_key: true,
          tracklet_id: "trackletId",
          view_id: "image",
        },
      ],
      track,
      item_id: "fleurs.jpg",
      view_id: "image",
      source_id: "Ground Truth",
      review_state: undefined,
      displayedMBox,
      features: {
        category_name: {
          name: "category_name",
          dtype: "str",
          value: "Type",
        },
        name: {
          name: "na",
          dtype: "str",
          value: "Vehicle",
        },
        category_id: {
          name: "category_id",
          dtype: "int",
          value: 2,
        },
      },
      highlighted: "all",
      displayControl: {
        hidden: false,
      },
    },
  ],
  embeddings: {},
};
