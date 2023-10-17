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
import { Library } from "@pixano/core";

const meta = {
  title: "Components/Core/Library",
  component: Library,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<Library>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    datasets: [
      {
        id: "dataset01",
        name: "Some dataset",
        description: "Dataset description",
        num_elements: 20,
        preview: "img-01.jpg",
        categories: [],
        page: {
          items: [
            [
              { name: "id", dtype: "text", value: "1" },
              { name: "view1", dtype: "image", value: "img-01.jpg" },
              { name: "view2", dtype: "image", value: "img-02.jpg" },
            ],
          ],
          total: 1,
        },
      },
      {
        id: "dataset02",
        name: "Another dataset",
        description: "Dataset description",
        num_elements: 50000,
        preview: "img-02.jpg",
        categories: [],
        page: {
          items: [
            [
              { name: "id", dtype: "text", value: "1" },
              { name: "view1", dtype: "image", value: "img-01.jpg" },
              { name: "view2", dtype: "image", value: "img-02.jpg" },
            ],
          ],
          total: 1,
        },
      },
      {
        id: "dataset03",
        name: "Yet another dataset",
        description: "Dataset description",
        num_elements: 1000,
        preview: "img-03.jpg",
        categories: [],
        page: {
          items: [
            [
              { name: "id", dtype: "text", value: "1" },
              { name: "view1", dtype: "image", value: "img-01.jpg" },
              { name: "view2", dtype: "image", value: "img-02.jpg" },
            ],
          ],
          total: 1,
        },
      },
      {
        id: "dataset04",
        name: "One final dataset",
        description: "Dataset description",

        num_elements: 20000,
        preview: "img-04.jpg",
        categories: [],
        page: {
          items: [
            [
              { name: "id", dtype: "text", value: "1" },
              { name: "view1", dtype: "image", value: "img-01.jpg" },
              { name: "view2", dtype: "image", value: "img-02.jpg" },
            ],
          ],
          total: 1,
        },
      },
    ],
    buttonLabel: "Explore",
  },
};
