/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// FIX IN FUTURE PR
import type { Meta, StoryObj } from "@storybook/svelte";

import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
import { interactiveSegmenterModel } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";

import { mockHandleSaveItem, MockInteractiveImageSegmenter } from "../../testing";
import { mockVideoDatasetItem } from "../../testing/datasets";

type Story = StoryObj<typeof meta>;

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Workspaces/VideoWorkspace",
  component: DatasetItemWorkspace,
  tags: ["autodocs"],
} satisfies Meta<DatasetItemWorkspace>;

export default meta;

const mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);

export const BasicVideoWorkspace: Story = {
  args: {
    canSaveCurrentItem: false,
    isLoading: false,
    shouldSaveCurrentItem: false,
    models: [],
    handleSaveItem: mockHandleSaveItem,
    selectedItem: mockVideoDatasetItem,
    featureValues: { main: {}, objects: {} },
  },
};
