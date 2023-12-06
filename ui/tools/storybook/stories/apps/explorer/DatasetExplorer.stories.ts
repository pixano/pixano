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
import { DatasetExplorer } from "@pixano/explorer";

const meta = {
  title: "Applications/Explorer/DatasetExplorer",
  component: DatasetExplorer,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<DatasetExplorer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    selectedTab: "dashboard",
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
      stats: [
        {
          name: "Some numerical statistics",
          type: "numerical",
          histogram: [
            { bin_start: 0.0, bin_end: 1.0, counts: 2, split: "train" },
            { bin_start: 1.0, bin_end: 2.0, counts: 4, split: "train" },
            { bin_start: 2.0, bin_end: 3.0, counts: 6, split: "train" },
            { bin_start: 3.0, bin_end: 4.0, counts: 8, split: "train" },
          ],
          range: [0.0, 10.0],
        },
        {
          name: "Some categorical statistics",
          type: "categorical",
          histogram: [
            { "Some categorical statistics": "a", counts: 2, split: "train" },
            { "Some categorical statistics": "b", counts: 4, split: "train" },
            { "Some categorical statistics": "c", counts: 6, split: "train" },
            { "Some categorical statistics": "d", counts: 8, split: "train" },
          ],
        },
      ],
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
    }, // storybook has no access to REST API...
    currentPage: 1,
  },
};
