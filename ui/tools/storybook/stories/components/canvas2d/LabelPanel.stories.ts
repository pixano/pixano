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
      views: {
        view: {
          id: "view",
          uri: "img-02.jpg",
        },
      },
      features: [
        { name: "id", dtype: "text", value: "1" },
        { name: "view", dtype: "image", value: "img-02.jpg" },
      ],
    },
    selectedDataset: {
      id: "euHS4xM5SSvQKAhmv3sFcp",
      name: "Dataset",
      description: "Dataset description",
      num_elements: 4,
      estimated_size: "N?A",
      preview: "",
      categories: [],
      page: {
        items: [
          [
            { name: "id", dtype: "text", value: "1" },
            { name: "view", dtype: "image", value: "img-02.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "2" },
            { name: "view", dtype: "image", value: "img-03.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "3" },
            { name: "view", dtype: "image", value: "img-05.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "4" },
            { name: "view", dtype: "image", value: "img-07.jpg" },
          ],
        ],
        total: 4,
      },
    },
    annotations: {
      "Ground truth": {
        id: "Ground truth",
        views: {
          view1: {
            id: "view",
            categories: {
              1: {
                id: 1,
                name: "eye",
                labels: {
                  "245": {
                    id: "245",
                    categoryId: 1,
                    categoryName: "eye",
                    sourceId: "Ground truth",
                    viewId: "view",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 2,
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
