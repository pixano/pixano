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
import { DatasetExplorer } from "@pixano/explorer";

const meta = {
  title: "Applications/Explorer/DatasetExplorer",
  component: DatasetExplorer,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<DatasetExplorer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    dataset: { id: "euHS4xM5SSvQKAhmv3sFcp" }, // storybook has no access to REST API...
  },
};
