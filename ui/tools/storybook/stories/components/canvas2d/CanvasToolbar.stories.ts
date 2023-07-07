/**
@copyright CEA-LIST/DIASI/SIALV/LVA (2023)
@author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
@license CECILL-C

This software is a collaborative computer program whose purpose is to
generate and explore labeled data for computer vision applications.
This software is governed by the CeCILL-C license under French law and
abiding by the rules of distribution of free software. You can use, 
modify and/ or redistribute the software under the terms of the CeCILL-C
license as circulated by CEA, CNRS and INRIA at the following URL

http://www.cecill.info
*/

import type { Meta, StoryObj } from "@storybook/svelte";
import CanvasToolbar from "../../../../../components/Canvas2D/src/CanvasToolbar.svelte";
import {
  ToolType,
  createLabeledPointTool,
  createMultiModalTool,
  createRectangleTool,
  createPanTool,
} from "../../../../../components/Canvas2D/src/tools";

const meta = {
  title: "Components/Canvas2D/CanvasToolbar",
  component: CanvasToolbar,
  tags: ["autodocs"],
} satisfies Meta<CanvasToolbar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicToolbar: Story = {
  args: {
    tools: [
      createMultiModalTool(ToolType.LabeledPoint, [
        createLabeledPointTool(1),
        createLabeledPointTool(0),
      ]),
      createRectangleTool(),
      createPanTool(),
    ],
  },
};
