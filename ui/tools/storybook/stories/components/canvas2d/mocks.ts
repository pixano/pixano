import type { InteractiveImageSegmenter, InteractiveImageSegmenterInput } from "@pixano/models/src/lib/interactive_image_segmentation"
// import { SegmentationResult } from "../../../../../components/models/src/interactive_image_segmentation";
import { maskDataToFortranArrayToRle } from "../../../../../components/models/src/mask_utils";
import { generatePolygonSegments, convertSegmentsToSVG } from "../../../../../components/models/src/tracer"



function flattenArray(image: number[][]): number[] {
    const flattenedArray: number[] = [];

    for (let y = 0; y < image.length; y++) {
        for (let x = 0; x < image[y].length; x++) {
            flattenedArray.push(image[y][x]);
        }
    }

    return flattenedArray;
}


export class MockInteractiveImageSegmenter implements InteractiveImageSegmenter {
    currentMask: Array<number> | null = null

    segmentImage(input: InteractiveImageSegmenterInput) {
        const image = input.image;
        const w = image.naturalWidth;
        const h = image.naturalHeight;

        if (!this.currentMask) {
            this.currentMask = new Array(w * h);
        }
        this.currentMask.fill(0);

        for (let i = 0; i < input.points.length; ++i) {
            const point = input.points[i];
            for (let y = 0; y < h; y++) {
                for (let x = 0; x < w; x++) {
                    const distanceX = x - point.x;
                    const distanceY = y - point.y;
                    const d = Math.sqrt(distanceX * distanceX + distanceY * distanceY);
                    if (d < 100) {
                        if (this.currentMask) this.currentMask[x + y * w] = 1;
                    }
                }
            }
        }

        if (input.box) {
            if (this.currentMask) {
                const xstart = Math.min(input.box.x, input.box.x + input.box.width);
                const width = Math.abs(input.box.width);
                const ystart = Math.min(input.box.y, input.box.y + input.box.height);
                const height = Math.abs(input.box.height);
                for(let i = xstart; i < xstart + width; i++) {
                    for(let j = ystart; j < ystart + height; j++) {
                        this.currentMask[i + j * w] = 1;
                    }
                }
            }
        }

        const maskRLE = maskDataToFortranArrayToRle(this.currentMask, h, w)
        //console.log(maskRLE)
        const maskPolygons = generatePolygonSegments(maskRLE, h);
        //console.log(maskPolygons);
        const masksSVG = convertSegmentsToSVG(maskPolygons);
        //console.log(masksSVG);
        //console.log(masksSVG.length);
        return { masksImage: masksSVG }
    }

    reset() {
        this.currentMask = null;
        console.log("Reset Mock Segmenter")
    }
}