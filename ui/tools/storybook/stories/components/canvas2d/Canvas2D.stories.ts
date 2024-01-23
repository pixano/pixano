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
import { Canvas2D, tools } from "@pixano/canvas2d";
import { utils } from "@pixano/core";

import * as mocks from "./mocks";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Canvas2D/Canvas2D",
  component: Canvas2D,
  tags: ["autodocs"],
} satisfies Meta<Canvas2D>;

export default meta;
type Story = StoryObj<typeof meta>;

// const embed = await fetch("image_moyenne.npy").then(response => response.arrayBuffer());
// initModel("sam_vit_b_01ec64.onnx");

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args

let catCol = utils.ordinalColorScale(["1", "2"]);

export const CanvasWithoutSelectedTool: Story = {
  args: {
    selectedItem: {
      id: "1",
      split: "val",
      views: {
        view1: {
          id: "view1",
          uri: "img-01.jpg",
          type: "image",
          features: {},
        },
        view2: {
          id: "view2",
          uri: "img-02.jpg",
          type: "image",
          features: {},
        },
      },
      features: {},
      objects: {},
      embeddings: {},
    },
    selectedTool: null,
    colorScale: catCol,
    masks: [],
    bboxes: [],
    embeddings: {},
    currentAnn: null,
  },
};

const segmenter = new mocks.MockInteractiveImageSegmenter();
let labeledPointCreator = tools.createPointSelectionTool();
labeledPointCreator.postProcessor = segmenter;

export const CanvasWithLabeledPointTool: Story = {
  args: {
    selectedItem: {
      id: "1",
      split: "val",
      views: {
        view1: {
          id: "view1",
          uri: "img-01.jpg",
          type: "image",
          features: {},
        },
        view2: {
          id: "view2",
          uri: "img-02.jpg",
          type: "image",
          features: {},
        },
      },
      features: {},
      objects: {},
      embeddings: {},
    },
    selectedTool: labeledPointCreator.modes[0],
    colorScale: catCol,
    masks: [],
    bboxes: [],
    embeddings: { view: [] },
    currentAnn: null,
  },
};

const rectangleCreator = tools.createRectangleTool();
rectangleCreator.postProcessor = segmenter;

export const CanvasWithRectangleTool: Story = {
  args: {
    selectedItem: {
      id: "1",
      split: "val",
      views: {
        view1: {
          id: "view1",
          uri: "img-01.jpg",
          type: "image",
          features: {},
        },
        view2: {
          id: "view2",
          uri: "img-02.jpg",
          type: "image",
          features: {},
        },
      },
      features: {},
      objects: {},
      embeddings: {},
    },
    selectedTool: rectangleCreator,
    colorScale: catCol,
    masks: [],
    bboxes: [],
    embeddings: { view: [] },
    currentAnn: null,
  },
};
