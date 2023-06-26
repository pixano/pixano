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
import AnnotationWorkspace from "../../../../../apps/annotator/src/lib/AnnotationWorkspace.svelte";
import { MockInteractiveImageSegmenter } from "../../components/canvas2d/mocks";
import { interactiveSegmenterModel } from "../../../../../apps/annotator/src/stores";

const meta = {
  title: "Applications/Annotator/AnnotationWorkspace",
  component: AnnotationWorkspace,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
} satisfies Meta<AnnotationWorkspace>;

export default meta;
type Story = StoryObj<typeof meta>;

let mock = new MockInteractiveImageSegmenter();
interactiveSegmenterModel.set(mock);

export const Base: Story = {
  args: {
    itemData: {
      dbName: "photos db",
      views: [
        {
          viewId: "view",
          imageURL: "img-02.jpg",
        },
      ],
      id: "id2684",
    },
    //sample for bear image "img-02.jpg"
    //bear left eye...
    masksGT: [
      {
        viewId: "view",
        id: "245",
        mask: [
          "M158 290 L158 297 159 302 160 302 160 304 159 304 159 311 160 314 161 315 162 317 164 317 164 318 165 320 166 321 167 322 178 322 178 321 179 320 180 319 181 317 182 316 183 315 184 313 185 311 186 310 187 308 188 306 189 305 190 304 191 302 192 299 193 299 193 298 192 298 191 294 190 291 189 289 188 287 187 285 186 284 186 283 184 283 183 282 183 281 180 281 180 280 172 280 172 281 169 281 169 282 167 282 167 283 165 283 165 284 163 284 162 285 162 286 160 286 159 288 158 290",
        ],
        visible: true,
        opacity: 1.0,
      },
    ],
    annotations: [
      {
        category_name: "eye",
        viewId: "view",
        items: [
          {
            id: "245",
            type: "mask",
            label: "eye-0",
            visible: true,
            opacity: 1.0,
          },
        ],
        visible: true,
      },
    ],
    embedding: [], //won't segment if embedding == null, so to let the mock "segment", give fake (unused) embedding
    dbImages: [
      "img-01.jpg",
      "img-02.jpg",
      "img-03.jpg",
      "img-04.jpg",
      "img-05.jpg",
      "img-06.jpg",
      "img-07.jpg",
      "img-08.jpg",
      "img-01.jpg",
      "img-02.jpg",
      "img-03.jpg",
      "img-04.jpg",
      "img-05.jpg",
      "img-06.jpg",
      "img-07.jpg",
      "img-08.jpg",
      "img-01.jpg",
      "img-02.jpg",
      "img-03.jpg",
      "img-04.jpg",
      "img-05.jpg",
      "img-06.jpg",
      "img-07.jpg",
      "img-08.jpg",
    ],
    classes: [
      { id: 0, name: "Dog" },
      { id: 1, name: "Cat" },
      { id: 2, name: "Person" },
      { id: 3, name: "Painting" },
    ],
  },
};
