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

import ImageWorkspace from "@pixano/imageworkspace/src/App.svelte";
import { interactiveSegmenterModel } from "@pixano/imageworkspace/src/lib/stores";

import { MockInteractiveImageSegmenter } from "../../components/canvas2d/mocks";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Image workspace/simple image",
  component: ImageWorkspace,
  tags: ["autodocs"],
} satisfies Meta<ImageWorkspace>;

export default meta;
type Story = StoryObj<typeof meta>;

const mock = new MockInteractiveImageSegmenter();
console.log({ mock });
interactiveSegmenterModel.set(mock);

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const SimpleImage: Story = {
  args: {
    selectedTool: null,
  },
};
