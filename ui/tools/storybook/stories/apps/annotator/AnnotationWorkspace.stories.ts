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
import { AnnotationWorkspace, stores } from "@pixano/annotator/";

import { MockInteractiveImageSegmenter } from "../../components/canvas2d/mocks";

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

const mock = new MockInteractiveImageSegmenter();
stores.interactiveSegmenterModel.set(mock);

export const Base: Story = {
  args: {
    selectedDataset: {
      id: "euHS4xM5SSvQKAhmv3sFcp",
      name: "Test dataset",
      description: "Test dataset description",
      estimated_size: "12.68 MB",
      num_elements: 4,
      preview: "",
      splits: ["val"],
      tables: {},
      categories: [],
      stats: [],
      page: {
        items: [
          {
            id: "1",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-01.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-02.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "2",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-03.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-04.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "3",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-05.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-06.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
          {
            id: "4",
            split: "val",
            views: {
              view1: {
                id: "view1",
                uri: "img-07.jpg",
                type: "image",
                features: {},
              },
              view2: {
                id: "view2",
                uri: "img-08.jpg",
                type: "image",
                features: {},
              },
            },
            features: {},
            objects: {},
            embeddings: {},
          },
        ],
        total: 4,
      },
    },
    selectedItem: {
      id: "1",
      split: "val",
      views: {
        view1: {
          id: "view1",
          uri: "img-01.jpg",
          type: "image",
          features: {},
        },
        view2: {
          id: "view2",
          uri: "img-02.jpg",
          type: "image",
          features: {},
        },
      },
      features: {},
      objects: {},
      embeddings: {},
    },
    annotations: {
      "Ground truth": {
        id: "Ground truth",
        views: {
          view1: {
            id: "view1",
            categories: {
              1: {
                id: 3,
                name: "tv",
                labels: {
                  "34646": {
                    id: "34646",
                    categoryId: 3,
                    categoryName: "tv",
                    sourceId: "Ground truth",
                    viewId: "view1",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 1,
            opened: true,
            visible: true,
          },
          view2: {
            id: "view2",
            categories: {
              1: {
                id: 1,
                name: "eye",
                labels: {
                  "587562": {
                    id: "587562",
                    categoryId: 1,
                    categoryName: "eye",
                    sourceId: "Ground truth",
                    viewId: "view2",
                    bboxOpacity: 1.0,
                    maskOpacity: 1.0,
                    visible: true,
                  },
                },
                opened: true,
                visible: true,
              },
            },
            numLabels: 1,
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
      { id: 0, name: "dog" },
      { id: 1, name: "eye" },
      { id: 2, name: "cat" },
      { id: 3, name: "tv" },
    ],
    masks: [
      {
        id: "34646",
        viewId: "view1",
        svg: [
          "M7 243 L7 261 36 261 36 262 78 262 78 263 84 263 84 262 95 262 95 261 107 261 107 260 118 260 118 259 130 259 130 258 141 258 141 257 153 257 153 256 154 234 155 202 156 202 156 173 142 173 142 172 114 172 114 171 86 171 86 170 58 170 58 169 29 169 29 168 10 168 9 171 8 207 7 243",
        ],
        catId: 3,
        visible: true,
        opacity: 1,
      },
      {
        id: "587562",
        viewId: "view2",
        svg: [
          "M158 290 L158 297 159 302 160 302 160 304 159 304 159 311 160 314 161 315 162 317 164 317 164 318 165 320 166 321 167 322 178 322 178 321 179 320 180 319 181 317 182 316 183 315 184 313 185 311 186 310 187 308 188 306 189 305 190 304 191 302 192 299 193 299 193 298 192 298 191 294 190 291 189 289 188 287 187 285 186 284 186 283 184 283 183 282 183 281 180 281 180 280 172 280 172 281 169 281 169 282 167 282 167 283 165 283 165 284 163 284 162 285 162 286 160 286 159 288 158 290",
        ],
        catId: 1,
        visible: true,
        opacity: 1.0,
      },
    ],
    bboxes: [
      {
        id: "34646",
        viewId: "view1",
        bbox: [7.03000009059906, 167.76000201702118, 149.32000160217285, 94.87000313401222],
        tooltip: "tv",
        catId: 3,
        visible: true,
        opacity: 1,
      },
      {
        id: "587562",
        viewId: "view2",
        bbox: [159.0000081062317, 278.99999618530273, 31.99999900907278, 45.999999046325684],
        tooltip: "eye",
        catId: 1,
        visible: true,
        opacity: 1,
      },
    ],
    currentPage: 1,
    models: ["sam_vit_h_4b8939.onnx"],
    saveFlag: false,
    activeLearningFlag: false,
  },
};
