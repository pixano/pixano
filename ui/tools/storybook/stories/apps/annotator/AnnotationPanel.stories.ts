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
import { AnnotationPanel } from "@pixano/annotator";
import { utils } from "@pixano/core";

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

let catCol = utils.getColor([1, 2]); // Define a color map for each category id

export const Base: Story = {
  args: {
    categoryColor: catCol,
    annotations: [
      {
        id: 1,
        name: "Dog",
        viewId: "view1",
        labels: [
          {
            id: "0x123",
            viewId: "view1",
            type: "mask",
            visible: true,
            opacity: 1.0,
          },
          {
            id: "0x354",
            viewId: "view1",
            type: "mask",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
      {
        id: 2,
        name: "Cat",
        viewId: "view1",
        labels: [
          {
            id: "0x237",
            viewId: "view1",
            type: "mask",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
      {
        id: 2,
        name: "Cat",
        viewId: "view2",
        labels: [
          {
            id: "0x487",
            viewId: "view2",
            type: "mask",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
    ],
    datasetItems: {
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
    currentPage: 1,
  },
};
