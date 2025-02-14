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
  mockFeaturesValues,
  mockHandleSaveItem,
  MockInteractiveImageSegmenter,
  mockVqaDatasetItem,
} from "../../testing";

type Story = StoryObj<typeof meta>;

const meta = {
  title: "Components/Workspaces/VqaWorkspace",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);
datasetSchemaStore.set(datasetSchema);

export const VqaWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    selectedItem: mockVqaDatasetItem,
    featureValues: mockFeaturesValues,
  },
};
