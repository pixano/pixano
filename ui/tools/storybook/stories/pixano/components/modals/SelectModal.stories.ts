/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
