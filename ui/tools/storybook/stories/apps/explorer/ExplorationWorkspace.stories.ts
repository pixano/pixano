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
import { ExplorationWorkspace } from "@pixano/explorer";

const meta = {
  title: "Applications/Explorer/ExplorationWorkspace",
  component: ExplorationWorkspace,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<ExplorationWorkspace>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Base: Story = {
  args: {
    selectedItem: {
      id: "1",
      views: {
        view: {
          id: "view",
          url: "img-02.jpg",
        },
      },
      features: [
        { name: "id", dtype: "text", value: "1" },
        { name: "view", dtype: "image", value: "img-02.jpg" },
      ],
    },
    //sample for bear image "img-02.jpg"
    //bear left eye...
    annotations: {
      "Ground truth": {
        id: "Ground truth",
        views: {
          view: {
            id: "view",
            categories: {
              1: {
                id: 1,
                name: "eye",
                labels: {
                  "245": {
                    id: "245",
                    categoryId: 1,
                    categoryName: "eye",
                    sourceId: "Ground truth",
                    viewId: "view",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 2,
            opened: true,
            visible: true,
          },
        },
        numLabels: 2,
        opened: true,
        visible: true,
      },
    },
    classes: [
      { id: 0, name: "Dog" },
      { id: 1, name: "eye" },
      { id: 2, name: "Cat" },
    ],
    masks: [
      {
        viewId: "view",
        catId: 1,
        id: "245",
        svg: [
          "M158 290 L158 297 159 302 160 302 160 304 159 304 159 311 160 314 161 315 162 317 164 317 164 318 165 320 166 321 167 322 178 322 178 321 179 320 180 319 181 317 182 316 183 315 184 313 185 311 186 310 187 308 188 306 189 305 190 304 191 302 192 299 193 299 193 298 192 298 191 294 190 291 189 289 188 287 187 285 186 284 186 283 184 283 183 282 183 281 180 281 180 280 172 280 172 281 169 281 169 282 167 282 167 283 165 283 165 284 163 284 162 285 162 286 160 286 159 288 158 290",
        ],
        visible: true,
        opacity: 1.0,
      },
    ],
    bboxes: [],
  },
};
