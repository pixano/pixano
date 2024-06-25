/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
