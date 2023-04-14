/**
@copyright CEA-LIST/DIASI/SIALV/LVA (2023)
@author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
@license CECILL-C

This software is a collaborative computer program whose purpose is to
generate and explore labeled data for computer vision applications.
This software is governed by the CeCILL-C license under French law and
abiding by the rules of distribution of free software. You can use, 
modify and/ or redistribute the software under the terms of the CeCILL-C
license as circulated by CEA, CNRS and INRIA at the following URL

http://www.cecill.info
*/

import type { Meta, StoryObj } from "@storybook/svelte";
import Library from "../../../../../apps/explorer/src/lib/Library.svelte";

const meta = {
  title: "Applications/Explorer/Library",
  component: Library,
  // This component will have an automatically generated Autodocs entry: https://storybook.js.org/docs/7.0/react/writing-docs/docs-page
  tags: ["autodocs"],
  parameters: {
    // More on how to position stories at: https://storybook.js.org/docs/7.0/svelte/configure/story-layout
    layout: "fullscreen",
  },
} satisfies Meta<Library>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    datasets: [
      {
        name: "fake_dataset_1",
        num_elements: 1000,
        preview:
          "https://tailwindui.com/img/ecommerce-images/product-page-01-related-product-01.jpg",
      },
      {
        name: "fake_dataset_2",
        num_elements: 50000,
        preview:
          "https://tailwindui.com/img/ecommerce-images/product-page-01-related-product-01.jpg",
      },
      {
        name: "fake_dataset_3",
        num_elements: 20000,
        preview:
          "https://tailwindui.com/img/ecommerce-images/product-page-01-related-product-01.jpg",
      },
    ],
  },
};
