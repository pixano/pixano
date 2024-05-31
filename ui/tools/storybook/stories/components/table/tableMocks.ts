import type { TableData } from "@pixano/core";

export const items: TableData = {
  cols: [
    {
      name: "id",
      type: "int",
    },
    {
      name: "split",
      type: "str",
    },
    {
      name: "image",
      type: "image",
    },
    {
      name: "video",
      type: "video",
    },
    {
      name: "categories",
      type: "histogram",
    },
  ],
  rows: [
    {
      id: "1",
      split: "val",
      image: "https://www.w3schools.com/tags/img_girl.jpg",
      video: "https://www.w3schools.com/html/mov_bbb.mp4",
      categories: {
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
    {
      id: "2",
      split: "val",
      image: "https://www.w3schools.com/tags/img_girl.jpg",
      video: "https://www.w3schools.com/html/mov_bbb.mp4",
      categories: {
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
    {
      id: "3",
      split: "val",
      image: "https://www.w3schools.com/tags/img_girl.jpg",
      video: "https://www.w3schools.com/html/mov_bbb.mp4",
      categories: {
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
};
