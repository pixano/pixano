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
import Library from "../../../../components/core/src/Library.svelte";


const meta = {
  title: "Components/Library",
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
        name: "Some dataset",
        num_elements: 20,
        preview: "img-01.jpg",
      },
      {
        name: "Another dataset",
        num_elements: 50000,
        preview: "img-02.jpg",
      },
      {
        name: "Yet another dataset",
        num_elements: 1000,
        preview: "img-03.jpg",
      },
      {
        name: "One final dataset",
        num_elements: 20000,
        preview: "img-04.jpg",
      },
    ],
    btn_label: "Explore"
  },
};
