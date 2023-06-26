import {
  type MaskRLE,
  type MaskSVG,
} from "../../../components/models/src/interactive_image_segmentation";

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
  catID: number;
  visible: boolean;
  opacity: number;
}

export interface BBox {
  viewId: string;
  id: string;
  bbox: Array<number>; //format xywh, normalized
  label: string;
  catID: number;
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
