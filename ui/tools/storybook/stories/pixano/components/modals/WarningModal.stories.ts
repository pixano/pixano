/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { Meta, StoryObj } from "@storybook/svelte";
import { WarningModal } from "@pixano/core";

const meta = {
  title: "Pixano/Components/Modals/WarningModal",
  component: WarningModal,
  tags: ["autodocs"],
} satisfies Meta<WarningModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicWarningModal: Story = {
  args: {
    message: "Some warning message",
    details: "Some details",
    moreDetails: "Some more details",
  },
};
