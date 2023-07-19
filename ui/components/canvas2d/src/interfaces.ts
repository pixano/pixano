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

// Imports
import type {
  MaskRLE,
  MaskSVG,
} from "../../../components/models/src/interactive_image_segmentation";

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

export interface MaskGT {
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

export interface AnnLabel {
  id: string;
  type: string; //bbox, mask, ...
  confidence?: number;
  label: string;
  visible: boolean;
  opacity: number;
}

export interface AnnotationsLabels {
  viewId: string;
  category_name: string;
  category_id: number;
  items: Array<AnnLabel>;
  visible: boolean;
}

export interface DBFeat {
  name: string;
  dtype: string;
  value: string;
}

export interface DatabaseFeats {
  items: Array<Array<DBFeat>>;
  total: number;
}
