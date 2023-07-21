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
    selectedDataset: {
      id: "euHS4xM5SSvQKAhmv3sFcp",
      name: "Dataset",
      description: "Dataset description",
      num_elements: 4,
      preview: "",
      categories: [],
      page: {
        items: [
          [
            { name: "id", dtype: "text", value: "1" },
            { name: "view1", dtype: "image", value: "img-01.jpg" },
            { name: "view2", dtype: "image", value: "img-02.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "2" },
            { name: "view1", dtype: "image", value: "img-03.jpg" },
            { name: "view2", dtype: "image", value: "img-04.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "3" },
            { name: "view1", dtype: "image", value: "img-05.jpg" },
            { name: "view2", dtype: "image", value: "img-06.jpg" },
          ],
          [
            { name: "id", dtype: "text", value: "4" },
            { name: "view1", dtype: "image", value: "img-07.jpg" },
            { name: "view2", dtype: "image", value: "img-08.jpg" },
          ],
        ],
        total: 4,
      },
    },
  },
};
