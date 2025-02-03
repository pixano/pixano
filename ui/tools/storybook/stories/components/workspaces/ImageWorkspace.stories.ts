/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// FIX IN FUTURE PR
import type { Meta, StoryObj } from "@storybook/svelte";

import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
import { interactiveSegmenterModel } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";
import { datasetSchema as datasetSchemaStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";

import {
  datasetSchema,
  mock16BitsImageDatasetItem,
  mockFeaturesValues,
  mockHandleSaveItem,
  mockImageDatasetItem,
  MockInteractiveImageSegmenter,
} from "../../testing";

type Story = StoryObj<typeof meta>;

const meta = {
  title: "Components/Workspaces/ImageWorkspace",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);
datasetSchemaStore.set(datasetSchema);

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
    selectedItem: mock16BitsImageDatasetItem,
    featureValues: mockFeaturesValues,
  },
};
