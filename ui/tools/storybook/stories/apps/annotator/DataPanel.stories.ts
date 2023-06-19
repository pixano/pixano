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
import DataPanel from "../../../../../apps/annotator/src/lib/DataPanel.svelte";

const meta = {
  title: "Applications/Annotator/DataPanel",
  component: DataPanel,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<DataPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    annotations: [
      { class: "Dog", items: [{ name: "dog-0" }, { name: "dog-1" }] },
      { class: "Cat", items: [{ name: "cat-0" }] },
    ],
    dataset: {
      items: [
        [{ value: "image 1" }, { value: "img-01.jpg" }],
        [{ value: "image 2" }, { value: "img-02.jpg" }],
        [{ value: "image 3" }, { value: "img-03.jpg" }],
        [{ value: "image 4" }, { value: "img-04.jpg" }],
        [{ value: "image 5" }, { value: "img-05.jpg" }],
        [{ value: "image 6" }, { value: "img-06.jpg" }],
        [{ value: "image 7" }, { value: "img-07.jpg" }],
        [{ value: "image 8" }, { value: "img-08.jpg" }],
      ],
    },
  },
};
