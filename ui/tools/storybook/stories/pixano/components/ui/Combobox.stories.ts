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
import { Combobox } from "@pixano/core";

const meta = {
  title: "Pixano/Components/UI/Combobox",
  component: Combobox,
  tags: ["autodocs"],
} satisfies Meta<Combobox>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicCombobox: Story = {
  args: {
    listItems: [
      { value: "value 1", label: "Some value" },
      { value: "value 2", label: "Another value" },
    ],
    placeholder: "Some placeholder",
  },
};
