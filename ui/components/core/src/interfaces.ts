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

// Exports

export interface StringDict<Type> {
  [key: string]: Type;
}

export interface NumberDict<Type> {
  [key: string]: Type;
}

export interface ItemData {
  id: string;
  views: StringDict<ViewData>;
  features: DatasetItem;
}

export interface ViewData {
  id: string;
  url: string;
  height: number;
  width: number;
}

export type ItemObjects = StringDict<StringDict<Array<ObjectData>>>;

export interface ObjectData {
  id: string;
  mask: MaskRLE;
  bbox: BBoxXYWH;
  category: CategoryData;
}

export interface CategoryData {
  id: number;
  name: string;
}

export interface Mask {
  id: string;
  viewId: string;
  svg: MaskSVG;
  rle?: MaskRLE;
  catId: number;
  visible: boolean;
  opacity: number;
}

export interface BBox {
  id: string;
  viewId: string;
  bbox: Array<number>;
  tooltip: string;
  catId: number;
  visible: boolean;
  opacity: number;
}

export type ItemLabels = StringDict<SourceLabels>;

export interface SourceLabels {
  id: string;
  views: StringDict<ViewLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface ViewLabels {
  id: string;
  categories: NumberDict<CategoryLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface CategoryLabels {
  id: number;
  name: string;
  labels: StringDict<Label>;
  opened: boolean;
  visible: boolean;
}

export interface Label {
  id: string;
  categoryId: number;
  categoryName: string;
  sourceId: string;
  viewId: string;
  confidence?: number;
  bboxOpacity: number;
  maskOpacity: number;
  visible: boolean;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  num_elements: number;
  preview: string;
  categories: any;
  page: DatasetItems;
}

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

export type DatasetItem = Array<DatasetItemFeature>;

export interface DatasetItemFeature {
  name: string;
  dtype: string;
  value: string;
}

export interface MaskRLE {
  counts: Array<number>;
  size: Array<number>;
}

export type MaskSVG = Array<string>;

export interface BBoxXYWH {
  x: number;
  y: number;
  width: number;
  height: number;
  predicted: boolean;
  confidence?: number;
}
