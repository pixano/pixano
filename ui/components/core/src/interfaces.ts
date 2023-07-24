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

export interface Dictionary<Type> {
  [key: string]: Type;
}

export interface ItemData {
  id: string;
  datasetId: string;
  filename?: string;
  height?: number;
  width?: number;
  views: Array<ViewData>;
  objects: Dictionary<ObjectsData>;
  catStats: Array<CategoryData>;
}

export interface ViewData {
  id: string;
  url: string;
}

export interface ObjectsData {
  id: string;
  masks: Array<MaskRLE>;
  bboxes: Array<BBoxXYWH>;
  categories: Array<CategoryData>;
}

export interface CategoryData {
  id: number;
  name: string;
  count: number;
}

export interface Mask {
  viewId: string;
  id: string;
  svg: MaskSVG;
  rle?: MaskRLE;
  catId: number;
  visible: boolean;
  opacity: number;
}

export interface BBox {
  viewId: string;
  id: string;
  bbox: Array<number>;
  tooltip: string;
  catId: number;
  visible: boolean;
}

export interface AnnotationLabel {
  id: string;
  viewId: string;
  type: string; //bbox, mask, ...
  confidence?: number;
  opacity: number;
  visible: boolean;
}

export interface AnnotationCategory {
  id: number;
  name: string;
  viewId: string;
  labels: Array<AnnotationLabel>;
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
  items: Array<Array<DatasetItemFeature>>;
  total: number;
}

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
