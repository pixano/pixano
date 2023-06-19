import { type MaskRLE, type MaskSVG } from "../../../components/models/src/interactive_image_segmentation"

export interface ItemData {
    dbName: string
    imageURL: string
    imageId: string
    viewId: string
}

export interface MaskGT {
    id: string
    mask: MaskSVG
    rle?: MaskRLE
    visible: boolean
    opacity: number
}

export interface BBox {
    id: string
    bbox: Array<number>  //format xywh, normalized
    label: string
    visible: boolean
}

export interface ItemLabel {
    id: string,
    label: string,
    visible: boolean
    opacity: number
}

export interface AnnotationsLabels {
    category: string
    category_id?: string
    items: Array<ItemLabel>
    visible: boolean
}