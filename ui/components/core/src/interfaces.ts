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
export interface ViewData {
  viewId: string;
  imageURL: string;
}
export interface ItemData {
  dbName: string;
  id: string;
  views: Array<ViewData>;
}

export interface Mask {
  viewId: string;
  id: string;
  mask: MaskSVG;
  rle?: MaskRLE;
  catId: number;
  visible: boolean;
  opacity: number;
}

export interface BBox {
  viewId: string;
  id: string;
  bbox: Array<number>; //format xywh, normalized
  label: string;
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

export interface DatasetItemFeature {
  name: string;
  dtype: string;
  value: string;
}

export interface DatasetItems {
  items: Array<Array<DatasetItemFeature>>;
  total: number;
}

export interface Dataset {
  id: string;
  name: string;
  description: string;
  num_elements: number;
  preview: string;
  categories: any;
  items: Array<Array<DatasetItemFeature>>;
}

export interface MaskRLE {
  counts: Array<number>;
  size: Array<number>;
}

export type MaskSVG = Array<string>;
