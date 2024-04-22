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

// Imports
import type { Meta, StoryObj } from "@storybook/svelte";
import { SelectModal } from "@pixano/core";

const meta = {
  title: "Pixano/Components/Modals/SelectModal",
  component: SelectModal,
  tags: ["autodocs"],
} satisfies Meta<SelectModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicSelectModal: Story = {
  args: {
    message: "Some message",
    choices: ["First choice", "Second choice", "Third choice"],
    selected: "Second choice",
  },
};

export const NoChoicesSelectModal: Story = {
  args: {
    message: "Some message",
    ifNoChoices: "No choices",
  },
};
