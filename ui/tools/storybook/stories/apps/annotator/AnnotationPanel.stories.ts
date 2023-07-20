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
import { AnnotationPanel } from "@pixano/annotator";
import { getColor } from "@pixano/core/src/utils";

const meta = {
  title: "Applications/Annotator/AnnotationPanel",
  component: AnnotationPanel,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<AnnotationPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

let catCol = getColor([1, 2]); // Define a color map for each category id

export const Base: Story = {
  args: {
    categoryColor: catCol,
    annotations: [
      {
        category_name: "Dog",
        category_id: 1,
        viewId: "view1",
        items: [
          {
            id: "0x123",
            type: "mask",
            label: "dog-0",
            visible: true,
            opacity: 1.0,
          },
          {
            id: "0x354",
            type: "mask",
            label: "dog-1",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
      {
        category_name: "Cat",
        category_id: 2,
        viewId: "view1",
        items: [
          {
            id: "0x237",
            type: "mask",
            label: "cat-0",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
      {
        category_name: "Cat",
        category_id: 2,
        viewId: "view2",
        items: [
          {
            id: "0x487",
            type: "mask",
            label: "cat-0",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
    ],
    dataset: {
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
    lastLoadedPage: 1,
  },
};
