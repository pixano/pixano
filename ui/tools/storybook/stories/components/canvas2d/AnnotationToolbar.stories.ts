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

import type { Meta, StoryObj } from "@storybook/svelte";
import { AnnotationToolbar, tools } from "@pixano/canvas2d";

const meta = {
  title: "Components/Canvas2D/AnnotationToolbar",
  component: AnnotationToolbar,
  tags: ["autodocs"],
} satisfies Meta<AnnotationToolbar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicToolbar: Story = {
  args: {
    tools_lists: [
      [tools.createPanTool()],
      [
        tools.createMultiModalTool(
          "Point selection",
          tools.ToolType.LabeledPoint,
          [tools.createLabeledPointTool(1), tools.createLabeledPointTool(0)]
        ),
        tools.createRectangleTool(),
        tools.createDeleteTool(),
      ],
    ],
  },
};
