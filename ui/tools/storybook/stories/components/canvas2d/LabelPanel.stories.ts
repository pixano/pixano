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

import type { Meta, StoryObj } from "@storybook/svelte";
import { LabelPanel } from "@pixano/canvas2d";
import { utils } from "@pixano/core";

const meta = {
  title: "Components/Canvas2D/LabelPanel",
  component: LabelPanel,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<LabelPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

let catCol = utils.ordinalColorScale(["1", "2"]); // Define a color map for each category id

export const Base: Story = {
  args: {
    selectedItem: {
      id: "1",
      split: "val",
      views: {
        view1: {
          id: "view1",
          uri: "img-01.jpg",
          type: "image",
          features: {},
        },
        view2: {
          id: "view2",
          uri: "img-02.jpg",
          type: "image",
          features: {},
        },
      },
      features: {},
      objects: {},
      embeddings: {},
    },
    selectedDataset: {
      id: "euHS4xM5SSvQKAhmv3sFcp",
      name: "Test dataset",
      description: "Test dataset description",
      estimated_size: "12.68 MB",
      num_elements: 4,
      preview: "",
      splits: ["val"],
      tables: {},
      categories: [],
      stats: [],
      page: {
        items: [
          {
            id: "1",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-01.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-02.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "2",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-03.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-04.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "3",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-05.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-06.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "4",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-07.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-08.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
        ],
        total: 4,
      },
    },
    annotations: {
      "Ground truth": {
        id: "Ground truth",
        views: {
          view1: {
            id: "view1",
            categories: {
              1: {
                id: 3,
                name: "tv",
                labels: {
                  "34646": {
                    id: "34646",
                    categoryId: 3,
                    categoryName: "tv",
                    sourceId: "Ground truth",
                    viewId: "view1",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 1,
            opened: true,
            visible: true,
          },
          view2: {
            id: "view2",
            categories: {
              1: {
                id: 1,
                name: "eye",
                labels: {
                  "587562": {
                    id: "587562",
                    categoryId: 1,
                    categoryName: "eye",
                    sourceId: "Ground truth",
                    viewId: "view2",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 1,
            opened: true,
            visible: true,
          },
        },
        numLabels: 2,
        opened: true,
        visible: true,
      },
    },
    currentPage: 1,
    colorScale: catCol,
    maskOpacity: 1.0,
    bboxOpacity: 0.0,
    confidenceThreshold: 0.0,
  },
};
