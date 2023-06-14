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
import { ImageDetails } from "@pixano/core";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Core/ImageDetails",
  component: ImageDetails,
  tags: ["autodocs"],
} satisfies Meta<ImageDetails>;

export default meta;
type Story = StoryObj<typeof meta>;

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const SingleView: Story = {
  args: {
    features: {
      id: "1",
      filename: "family.jpg",
      width: 960,
      height: 640,
      views: {
        family: {
          image: "family.jpg",
          objects: {
            category: [
              { id: 1, name: "woman" },
              { id: 2, name: "child" },
              { id: 3, name: "dog" },
              { id: 2, name: "child" },
              { id: 4, name: "man" },
            ],
            boundingBox: [
              {
                x: 0.15,
                y: 0.25,
                width: 0.15,
                height: 0.27,
                is_predict: true,
                confidence: 0.5,
              },
              {
                x: 0.25,
                y: 0.2,
                width: 0.12,
                height: 0.21,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.41,
                y: 0.4,
                width: 0.13,
                height: 0.18,
                is_predict: true,
                confidence: 0.75,
              },
              {
                x: 0.5,
                y: 0.12,
                width: 0.16,
                height: 0.28,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.65,
                y: 0.18,
                width: 0.17,
                height: 0.36,
                is_predict: true,
                confidence: 0.3,
              },
            ],
            segmentation: [
              [[0.15, 0.25, 0.3, 0.25, 0.3, 0.52, 0.15, 0.52]],
              [[0.25, 0.2, 0.37, 0.2, 0.37, 0.41, 0.25, 0.41]],
              [[0.41, 0.4, 0.54, 0.4, 0.54, 0.58, 0.41, 0.58]],
              [[0.5, 0.12, 0.66, 0.12, 0.66, 0.4, 0.5, 0.4]],
              [[0.65, 0.18, 0.82, 0.18, 0.82, 0.54, 0.65, 0.54]],
            ],
          },
        },
      },
      categoryStats: [
        { id: 1, name: "woman", count: 1 },
        { id: 2, name: "child", count: 2 },
        { id: 3, name: "dog", count: 1 },
        { id: 4, name: "man", count: 1 },
      ],
    },
  },
};

export const MultiView: Story = {
  args: {
    features: {
      id: "1",
      filename: "family.jpg",
      width: 960,
      height: 640,
      views: {
        default: {
          image: "family.jpg",
          objects: {
            category: [
              { id: 1, name: "woman" },
              { id: 2, name: "child" },
              { id: 3, name: "dog" },
              { id: 2, name: "child" },
              { id: 4, name: "man" },
            ],
            boundingBox: [
              {
                x: 0.15,
                y: 0.25,
                width: 0.15,
                height: 0.27,
                is_predict: true,
                confidence: 0.5,
              },
              {
                x: 0.25,
                y: 0.2,
                width: 0.12,
                height: 0.21,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.41,
                y: 0.4,
                width: 0.13,
                height: 0.18,
                is_predict: true,
                confidence: 0.75,
              },
              {
                x: 0.5,
                y: 0.12,
                width: 0.16,
                height: 0.28,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.65,
                y: 0.18,
                width: 0.17,
                height: 0.36,
                is_predict: true,
                confidence: 0.3,
              },
            ],
            segmentation: [
              [[0.15, 0.25, 0.3, 0.25, 0.3, 0.52, 0.15, 0.52]],
              [[0.25, 0.2, 0.37, 0.2, 0.37, 0.41, 0.25, 0.41]],
              [[0.41, 0.4, 0.54, 0.4, 0.54, 0.58, 0.41, 0.58]],
              [[0.5, 0.12, 0.66, 0.12, 0.66, 0.4, 0.5, 0.4]],
              [[0.65, 0.18, 0.82, 0.18, 0.82, 0.54, 0.65, 0.54]],
            ],
          },
        },
        upside_down: {
          image: "family_grey_upside_down.jpg",
          objects: {
            category: [
              { id: 1, name: "woman" },
              { id: 2, name: "child" },
              { id: 3, name: "dog" },
              { id: 2, name: "child" },
              { id: 4, name: "man" },
            ],
            boundingBox: [
              {
                x: 0.7,
                y: 0.48,
                width: 0.15,
                height: 0.27,
                is_predict: true,
                confidence: 0.5,
              },
              {
                x: 0.63,
                y: 0.59,
                width: 0.12,
                height: 0.21,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.46,
                y: 0.42,
                width: 0.13,
                height: 0.18,
                is_predict: true,
                confidence: 0.75,
              },
              {
                x: 0.34,
                y: 0.6,
                width: 0.16,
                height: 0.28,
                is_predict: false,
                confidence: 1,
              },
              {
                x: 0.18,
                y: 0.46,
                width: 0.17,
                height: 0.36,
                is_predict: true,
                confidence: 0.3,
              },
            ],
            segmentation: [
              [[0.7, 0.48, 0.85, 0.48, 0.85, 0.75, 0.7, 0.75]],
              [[0.63, 0.59, 0.75, 0.59, 0.75, 0.8, 0.63, 0.8]],
              [[0.46, 0.42, 0.59, 0.42, 0.59, 0.6, 0.46, 0.6]],
              [[0.34, 0.6, 0.5, 0.6, 0.5, 0.88, 0.34, 0.88]],
              [[0.18, 0.46, 0.35, 0.46, 0.35, 0.82, 0.18, 0.82]],
            ],
          },
        },
        zoom_man: {
          image: "man.png",
          objects: {
            category: [{ id: 4, name: "man" }],
            boundingBox: [
              {
                x: 0,
                y: 0,
                width: 1,
                height: 1,
                is_predict: false,
                confidence: 1,
              },
            ],
            segmentation: [[[0, 0, 1, 0, 1, 1, 0, 1]]],
          },
        },
        zoom_woman: {
          image: "woman.png",
          objects: {
            category: [{ id: 1, name: "woman" }],
            boundingBox: [
              {
                x: 0,
                y: 0,
                width: 1,
                height: 1,
                is_predict: false,
                confidence: 1,
              },
            ],
            segmentation: [[[0, 0, 1, 0, 1, 1, 0, 1]]],
          },
        },
      },
      categoryStats: [
        { id: 1, name: "woman", count: 3 },
        { id: 2, name: "child", count: 4 },
        { id: 3, name: "dog", count: 2 },
        { id: 4, name: "man", count: 3 },
      ],
    },
  },
};
