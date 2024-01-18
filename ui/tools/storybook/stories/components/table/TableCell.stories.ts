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
import { TableCell } from "@pixano/table";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Table/TableCell",
  component: TableCell,
  tags: ["autodocs"],
} satisfies Meta<TableCell>;

export default meta;
type Story = StoryObj<typeof meta>;

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const Text: Story = {
  args: {
    itemFeature: {
      name: "text cell",
      dtype: "str",
      value: "This is a text cell.",
    },
  },
};

export const Int: Story = {
  args: {
    itemFeature: {
      name: "int cell",
      dtype: "float",
      value: 54,
    },
  },
};

export const Float: Story = {
  args: {
    itemFeature: {
      name: "float cell",
      dtype: "float",
      value: 5.4,
    },
  },
};

export const Image: Story = {
  args: {
    itemFeature: {
      name: "image cell",
      dtype: "image",
      value: "http://farm4.staticflickr.com/3796/9478086045_6c5580fb62_z.jpg",
    },
  },
};

export const Video: Story = {
  args: {
    itemFeature: {
      name: "video cell",
      dtype: "video",
      value: "https://www.w3schools.com/html/mov_bbb.mp4",
    },
  },
};

export const Histogram: Story = {
  args: {
    itemFeature: {
      name: "histogram cell",
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
};
