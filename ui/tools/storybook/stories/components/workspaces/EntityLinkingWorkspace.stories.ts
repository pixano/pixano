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
  mockFeaturesValues,
  mockHandleSaveItem,
  MockInteractiveImageSegmenter,
} from "../../testing";
import { mockEntityLinkingDatasetItem } from "../../testing/datasets";
import { datasetSchema } from "../../testing/datasetSchema";

type Story = StoryObj<typeof meta>;

const meta = {
  title: "Components/Workspaces/EntityLinkingWorkspace",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);
datasetSchemaStore.set(datasetSchema);

export const EntityLinkingWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    selectedItem: mockEntityLinkingDatasetItem,
    featureValues: mockFeaturesValues,
  },
};
