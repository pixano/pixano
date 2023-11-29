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

export interface Dict<Type> {
  [key: string]: Type;
}

export interface ItemDetails {
  itemData: ItemData;
  itemObjects: Array<ObjectData>;
}

export interface ItemData {
  id: string;
  views: Dict<ViewData>;
  features: DatasetItem;
}

export interface ViewData {
  id: string;
  uri: string;
  height?: number;
  width?: number;
}

export interface ObjectData {
  id: string;
  item_id: string;
  source_id: string;
  view_id: string;
  mask: MaskRLE;
  bbox: BBoxXYWH;
  category_id: number;
  category_name: string;
  attributes: string;
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

export type ItemLabels = Dict<SourceLabels>;

export interface SourceLabels {
  id: string;
  views: Dict<ViewLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface ViewLabels {
  id: string;
  categories: Dict<CategoryLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface CategoryLabels {
  id: number;
  name: string;
  labels: Dict<Label>;
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
  attributes?: string;
  bboxOpacity: number;
  maskOpacity: number;
  visible: boolean;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  num_elements: number;
  estimated_size: string;
  preview: string;
  categories: Array<CategoryData>;
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
  value: number | string | Stats;
}

export interface MaskRLE {
  counts: Array<number>;
  size: Array<number>;
}

export type MaskSVG = Array<string>;

export interface BBoxXYWH {
  coords: Array<number>;
  format: string;
  confidence: number;
}

export interface Stats {
  name: string;
  type: string;
  range?: Array<number>;
  histogram: Array<Dict<number | string | boolean>>;
}
