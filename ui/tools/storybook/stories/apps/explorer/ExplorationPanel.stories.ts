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
import { ExplorationPanel } from "@pixano/explorer";
import { utils } from "@pixano/core";

const meta = {
  title: "Applications/Explorer/ExplorationPanel",
  component: ExplorationPanel,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<ExplorationPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

let catCol = utils.colorLabel([1, 2]); // Define a color map for each category id

export const Base: Story = {
  args: {
    selectedItem: {
      id: "1",
      views: [
        {
          id: "view",
          url: "img-02.jpg",
        },
      ],
      features: [
        { name: "id", dtype: "text", value: "1" },
        { name: "view", dtype: "image", value: "img-02.jpg" },
      ],
    },
    annotations: {
      "Ground truth": {
        id: "Ground truth",
        views: {
          view1: {
            id: "view",
            categories: {
              eye: {
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
    labelColors: catCol,
    maskOpacity: 1.0,
    bboxOpacity: 0.0,
    confidenceThreshold: 0.0,
  },
};
