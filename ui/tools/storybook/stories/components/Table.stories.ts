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
import { Table } from "@pixano/core";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Table",
  component: Table,
  tags: ["autodocs"],
} satisfies Meta<Table>;

export default meta;
type Story = StoryObj<typeof meta>;

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const Base: Story = {
  args: {
    featureNames: [
      { name: "id", type: "number" },
      { name: "image", type: "image" },
      { name: "description", type: "text" },
      { name: "graph", type: "histogram" },
    ],
    features: [
      [
        { dtype: "number", value: 10 },
        {
          dtype: "image",
          value:
            "http://farm4.staticflickr.com/3796/9478086045_6c5580fb62_z.jpg",
        },
        { dtype: "text", value: "A boat on a lake, with some swans." },
        {
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
      ],
      [
        { dtype: "number", value: 65 },
        {
          dtype: "image",
          value:
            "http://farm4.staticflickr.com/3284/5710807775_555410e5b1_z.jpg",
        },
        {
          dtype: "text",
          value: "An upside-down broccoli surrounded by glasses.",
        },
        {
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
      ],
    ],
  },
};
