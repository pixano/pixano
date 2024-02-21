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
import { ConfirmModal } from "@pixano/core";

const meta = {
  title: "Components/Core/Modals/ConfirmModal",
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
