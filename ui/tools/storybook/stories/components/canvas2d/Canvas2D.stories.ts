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
import Canvas2D from "../../../../../components/Canvas2D/src/Canvas2D.svelte";
import {
  createLabeledPointTool,
  createRectangleTool,
} from "../../../../../components/Canvas2D/src/tools";
import { drawLabel } from "../../../../../components/core/src/konva_utils";
import * as mocks from "./mocks";

//import { initModel } from "../../../../../apps/annotator/src/lib/sam_api"

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
export const CanvasWithoutSelectedTool: Story = {
  args: {
    views: [
      {
        viewId: "view",
        imageURL: "image_moyenne.jpg",
      },
    ],
    imageId: "image_moyenne",
    masksGT: null,
    bboxes: null,
    selectedTool: null,
    prediction: null,
  },
};

const segmenter = new mocks.MockInteractiveImageSegmenter();
let labeledPointCreator = createLabeledPointTool(1);
labeledPointCreator.postProcessor = segmenter;

export const CanvasWithLabeledPointTool: Story = {
  args: {
    views: [
      {
        viewId: "view",
        imageURL: "image_moyenne.jpg",
      },
    ],
    imageId: "image_moyenne",
    masksGT: null,
    bboxes: null,
    prediction: null,
    selectedTool: labeledPointCreator,
  },
};

let rectangleCreator = createRectangleTool();
rectangleCreator.postProcessor = segmenter;

export const CanvasWithRectangleTool: Story = {
  args: {
    views: [
      {
        viewId: "view",
        imageURL: "image_moyenne.jpg",
      },
    ],
    imageId: "image_moyenne",
    masksGT: null,
    bboxes: null,
    prediction: null,
    selectedTool: rectangleCreator,
  },
};
