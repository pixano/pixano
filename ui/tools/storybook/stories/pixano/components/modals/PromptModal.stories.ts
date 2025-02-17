/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { Meta, StoryObj } from "@storybook/svelte";

import { PromptModal } from "@pixano/core";

const meta = {
  title: "Pixano/Components/Modals/PromptModal",
  component: PromptModal,
  tags: ["autodocs"],
} satisfies Meta<PromptModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicPromptModal: Story = {
  args: {
    message: "Some message",
    placeholder: "Some placeholder",
  },
};
