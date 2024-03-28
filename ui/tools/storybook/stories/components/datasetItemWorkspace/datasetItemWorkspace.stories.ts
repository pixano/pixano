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

// FIX IN FUTURE PR
import type { Meta, StoryObj } from "@storybook/svelte";

import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
import { interactiveSegmenterModel } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

import { MockInteractiveImageSegmenter } from "./mocks";
import {
  mockedImageDatasetItem,
  mockedCurrentDataset,
  mockHandleSaveItem,
  mockedVideoDatasetItem,
  mockedVideoDatasetItemWithMask,
} from "./datasetItemWorkspaceMocks";

type Story = StoryObj<typeof meta>;

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Dataset Item",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;
// type Story = StoryObj<typeof meta>;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args

export const BasicImageWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    currentDataset: mockedCurrentDataset,
    selectedItem: mockedImageDatasetItem,
  },
};

export const SimpleVideo: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    currentDataset: mockedCurrentDataset,
    selectedItem: mockedVideoDatasetItem,
  },
};

export const VideoWithMask: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    currentDataset: mockedCurrentDataset,
    selectedItem: mockedVideoDatasetItemWithMask,
  },
};
