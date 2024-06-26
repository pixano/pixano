/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { Meta, StoryObj } from "@storybook/svelte";
import { ConfirmModal } from "@pixano/core";

const meta = {
  title: "Pixano/Components/Modals/ConfirmModal",
  component: ConfirmModal,
  tags: ["autodocs"],
} satisfies Meta<ConfirmModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicConfirmModal: Story = {
  args: { message: "Some message" },
};

export const ConfirmModalWithDetails: Story = {
  args: { message: "Some message", details: "Some details" },
};

export const ConfirmModalWithAlternativeAction: Story = {
  args: { message: "Some message", alternativeAction: "Some alternative action" },
};
