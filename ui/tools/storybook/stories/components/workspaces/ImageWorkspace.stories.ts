/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// FIX IN FUTURE PR
import type { Meta, StoryObj } from "@storybook/svelte";

import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
import { interactiveSegmenterModel } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

import {
  mock16BitImageDatasetItem,
  mockFeaturesValues,
  mockHandleSaveItem,
  MockInteractiveImageSegmenter,
} from "../../testing";
import { mockImageDatasetItem } from "../../testing/datasets";

type Story = StoryObj<typeof meta>;

const meta = {
  title: "Components/Workspaces/ImageWorkspace",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);

export const BasicImageWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    selectedItem: mockImageDatasetItem,
    featureValues: mockFeaturesValues,
  },
};

export const SixteenBitImageWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    selectedItem: mock16BitImageDatasetItem,
    featureValues: mockFeaturesValues,
  },
};
