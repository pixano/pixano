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

// DATASET

export interface DatasetInfo {
  id: string;
  name: string;
  description: string;
  estimated_size: string;
  num_elements: number;
  preview: string;
  splits: Array<string>;
  tables: Record<string, Array<DatasetTable>>;
  categories: Array<DatasetCategory>;
  stats: Array<DatasetStat>;
  page?: DatasetItems;
}

export interface DatasetTable {
  name: string;
  fields: Record<string, string>;
  source?: string;
  type?: string;
}

export interface DatasetCategory {
  id: number;
  name: string;
}

export interface DatasetStat {
  name: string;
  type: string;
  histogram: Array<Record<string, number | string | boolean>>;
  range?: Array<number>;
}

// DATASET ITEM

export interface DatasetItem {
  id: string;
  split: string;
  views: Record<string, ItemView>;
  objects: Record<string, ItemObject>;
  features: Record<string, ItemFeature>;
  embeddings: Record<string, ItemEmbedding>;
}

export interface DatasetItems {
  items: Array<DatasetItem>;
  total: number;
}

// ITEM DATA

export interface ItemView {
  id: string;
  type: string;
  uri: string;
  thumbnail?: string;
  frame_number?: number;
  total_frames?: number;
  features: Record<string, ItemFeature>;
}

// ITEM OBJECT

export interface ItemObject {
  id: string;
  item_id: string;
  source_id: string;
  view_id: string;
  mask: ItemURLE;
  bbox: ItemBBox;
  features: Record<string, ItemFeature>;
}

export interface ItemURLE {
  counts: Array<number>;
  size: Array<number>;
}

export interface ItemBBox {
  coords: Array<number>;
  format: string;
  is_normalized: boolean;
  confidence: number;
}

// ITEM EMBEDDING

export interface ItemEmbedding {
  view_id: string;
  data: string;
}

// ITEM FEATURE

export interface ItemFeature {
  name: string;
  dtype: string;
  value: number | string | boolean | DatasetStat;
}

// UI DATA

export interface Mask {
  id: string;
  viewId: string;
  svg: MaskSVG;
  rle?: ItemURLE;
  catId: number;
  visible: boolean;
  opacity: number;
}

export type MaskSVG = Array<string>;

export interface BBox {
  id: string;
  viewId: string;
  bbox: Array<number>;
  tooltip: string;
  catId: number;
  visible: boolean;
  opacity: number;
}

// LABELS DATA

export type ItemLabels = Record<string, SourceLabels>;

export interface SourceLabels {
  id: string;
  views: Record<string, ViewLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface ViewLabels {
  id: string;
  categories: Record<string, CategoryLabels>;
  numLabels: number;
  opened: boolean;
  visible: boolean;
}

export interface CategoryLabels {
  id: number;
  name: string;
  labels: Record<string, Label>;
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
