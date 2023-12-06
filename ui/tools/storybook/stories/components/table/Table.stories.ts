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
import { Table } from "@pixano/table";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Table/Table",
  component: Table,
  tags: ["autodocs"],
} satisfies Meta<Table>;

export default meta;
type Story = StoryObj<typeof meta>;

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const ImageTable: Story = {
  args: {
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
  },
};

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const AllFeaturesTable: Story = {
  args: {
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
        features: {
          hist1: {
            name: "hist1",
            dtype: "histogram",
            value: {
              name: "categories",
              type: "categorical",
              histogram: [
                { categories: "woman", counts: 838421, split: "train" },
                { categories: "man", counts: 738421, split: "train" },
                { categories: "car", counts: 19901, split: "train" },
                { categories: "dog", counts: 300000, split: "train" },
                { categories: "cat", counts: 150000, split: "train" },
              ],
            },
          },
        },
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
        features: {
          hist1: {
            name: "hist1",
            dtype: "histogram",
            value: {
              name: "categories",
              type: "categorical",
              histogram: [
                { categories: "woman", counts: 838421, split: "train" },
                { categories: "man", counts: 738421, split: "train" },
                { categories: "car", counts: 19901, split: "train" },
                { categories: "dog", counts: 300000, split: "train" },
                { categories: "cat", counts: 150000, split: "train" },
              ],
            },
          },
        },
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
        features: {
          hist1: {
            name: "hist1",
            dtype: "histogram",
            value: {
              name: "categories",
              type: "categorical",
              histogram: [
                { categories: "woman", counts: 838421, split: "train" },
                { categories: "man", counts: 738421, split: "train" },
                { categories: "car", counts: 19901, split: "train" },
                { categories: "dog", counts: 300000, split: "train" },
                { categories: "cat", counts: 150000, split: "train" },
              ],
            },
          },
        },
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
        features: {
          hist1: {
            name: "hist1",
            dtype: "histogram",
            value: {
              name: "categories",
              type: "categorical",
              histogram: [
                { categories: "woman", counts: 838421, split: "train" },
                { categories: "man", counts: 738421, split: "train" },
                { categories: "car", counts: 19901, split: "train" },
                { categories: "dog", counts: 300000, split: "train" },
                { categories: "cat", counts: 150000, split: "train" },
              ],
            },
          },
        },
        objects: {},
        embeddings: {},
      },
    ],
  },
};
