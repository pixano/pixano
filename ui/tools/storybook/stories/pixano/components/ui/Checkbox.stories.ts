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
import { Checkbox } from "@pixano/core";

const meta = {
  title: "Pixano/Components/UI/Checkbox",
  component: Checkbox,
  tags: ["autodocs"],
} satisfies Meta<Checkbox>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicCheckbox: Story = {
  args: {
    title: "Some title",
  },
};

export const DisabledCheckbox: Story = {
  args: {
    title: "test",
    disabled: "true",
  },
};
