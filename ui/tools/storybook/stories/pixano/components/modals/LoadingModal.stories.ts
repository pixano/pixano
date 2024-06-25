/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { Meta, StoryObj } from "@storybook/svelte";
import { LoadingModal } from "@pixano/core";

const meta = {
  title: "Pixano/Components/Modals/LoadingModal",
  component: LoadingModal,
  tags: ["autodocs"],
} satisfies Meta<LoadingModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicLoadingModal: Story = {};
