import { type MaskRLE, type MaskSVG } from "../../../../components/models/src/interactive_image_segmentation"

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
}

export interface ItemLabel {
    id: string,
    label: string,
    visible: boolean
}

export interface AnnotationsLabels {
    class: string
    items: Array<ItemLabel>
    visible: boolean
}