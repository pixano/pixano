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
import Canvas2D from "../../../../../components/Canvas2D/src/Canvas2D.svelte"
import { createLabeledPointTool, createRectangleTool } from "../../../../../components/Canvas2D/src/tools";
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

// //TMP: help log
// const log_help = false;
// if(log_help) {
//   console.log("Usage:");
//   console.log("  click to add points (+/-) in point mode, drag to draw a bow in box mode");
//   console.log("  prediction is done on each new/modified input");
//   console.log("  drag a point to move it (continuously predict while dragging)");
//   console.log("Keys:");
//   console.log("  Shift: toggle to point mode, switch between point + / point -");
//   console.log("  Ctrl: toggle to box mode");
//   console.log("  c: clear output (input and mask)");
//   console.log("  Suppr: remove highlighted point");
//   console.log("  (dev) i: get info");
//   console.log("  (dev) Alt: toggle Hover mode");
//   }

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const CanvasWithoutSelectedTool: Story = {
  args: {
    imageURL: "image_moyenne.jpg",
    imageId: "image_moyenne",
    viewId: "view",
    masksGT: [],
    selectedTool: null
  },
};

const segmenter = new mocks.MockInteractiveImageSegmenter();
let labeledPointCreator = createLabeledPointTool(1);
labeledPointCreator.postProcessor = segmenter;

export const CanvasWithLabeledPointTool: Story = {
  args: {
    imageURL: "image_moyenne.jpg",
    imageId: "image_moyenne",
    viewId: "view",
    masksGT: [],
    selectedTool: labeledPointCreator
  },
};

let rectangleCreator = createRectangleTool();
rectangleCreator.postProcessor = segmenter;

export const CanvasWithRectangleTool: Story = {
  args: {
    imageURL: "image_moyenne.jpg",
    imageId: "image_moyenne",
    viewId: "view",
    masksGT: [],
    selectedTool: rectangleCreator
  },
};
