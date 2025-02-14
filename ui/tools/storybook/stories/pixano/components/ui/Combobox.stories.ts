/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
