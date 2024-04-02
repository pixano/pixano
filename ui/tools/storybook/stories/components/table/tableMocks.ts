// import type { DatasetItem } from "@pixano/core";

import type { ItemFeature } from "@pixano/core";

export const items: Array<Array<ItemFeature>> = [
  [
    {
      name: "id",
      dtype: "int",
      value: "1",
    },
    {
      name: "split",
      dtype: "str",
      value: "val",
    },
    {
      name: "image",
      dtype: "image",
      value: "https://www.w3schools.com/tags/img_girl.jpg",
    },
    {
      name: "video",
      dtype: "video",
      value: "https://www.w3schools.com/html/mov_bbb.mp4",
    },
    {
      name: "categories",
      dtype: "histogram",
      value: {
        name: "categories",
        type: "categorical",
        histogram: [
          { categories: "woman", counts: 838421, split: "train" },
          { categories: "man", counts: 738421, split: "train" },
          { categories: "car", counts: 19901, split: "train" },
          { categories: "dog", counts: 300000, split: "train" },
          { categories: "cat", counts: 150000, split: "train" },
        ],
      },
    },
  ],
  [
    {
      name: "id",
      dtype: "int",
      value: "2",
    },
    {
      name: "split",
      dtype: "str",
      value: "val",
    },
    {
      name: "image",
      dtype: "image",
      value: "https://www.w3schools.com/tags/img_girl.jpg",
    },
    {
      name: "video",
      dtype: "video",
      value: "https://www.w3schools.com/html/mov_bbb.mp4",
    },
    {
      name: "categories",
      dtype: "histogram",
      value: {
        name: "categories",
        type: "categorical",
        histogram: [
          { categories: "woman", counts: 838421, split: "train" },
          { categories: "man", counts: 738421, split: "train" },
          { categories: "car", counts: 19901, split: "train" },
          { categories: "dog", counts: 300000, split: "train" },
          { categories: "cat", counts: 150000, split: "train" },
        ],
      },
    },
  ],
  [
    {
      name: "id",
      dtype: "int",
      value: "3",
    },
    {
      name: "split",
      dtype: "str",
      value: "val",
    },
    {
      name: "image",
      dtype: "image",
      value: "https://www.w3schools.com/tags/img_girl.jpg",
    },
    {
      name: "video",
      dtype: "video",
      value: "https://www.w3schools.com/html/mov_bbb.mp4",
    },
    {
      name: "categories",
      dtype: "histogram",
      value: {
        name: "categories",
        type: "categorical",
        histogram: [
          { categories: "woman", counts: 838421, split: "train" },
          { categories: "man", counts: 738421, split: "train" },
          { categories: "car", counts: 19901, split: "train" },
          { categories: "dog", counts: 300000, split: "train" },
          { categories: "cat", counts: 150000, split: "train" },
        ],
      },
    },
  ],
];