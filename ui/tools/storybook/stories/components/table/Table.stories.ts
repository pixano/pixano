/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Meta, StoryObj } from "@storybook/svelte";
import { Table } from "@pixano/table";
import { items } from "./tableMocks";

// More on how to set up stories at: https://storybook.js.org/docs/7.0/svelte/writing-stories/introduction
const meta = {
  title: "Components/Table/Table",
  component: Table,
  tags: ["autodocs"],
} satisfies Meta<Table>;

export default meta;
type Story = StoryObj<typeof meta>;

// More on writing stories with args: https://storybook.js.org/docs/7.0/svelte/writing-stories/args
export const BasicTable: Story = {
  args: {
    items,
  },
};
