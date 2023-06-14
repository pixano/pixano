export interface ItemData {
    dbName: string
    imageURL: string
    imageId: string
    viewId: string
}

export interface MaskRLE {
    counts: Array<number>
    size: Array<number>
}

export interface MaskGT {
    id: string
    mask: any  //maskSVG
    rle?: MaskRLE   //maskRLE
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