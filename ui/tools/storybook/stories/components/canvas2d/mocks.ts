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

// Imports
import { mask_utils } from "@pixano/models";

import type {
  InteractiveImageSegmenter,
  InteractiveImageSegmenterInput,
} from "@pixano/models";

function flattenArray(image: number[][]): number[] {
  const flattenedArray: number[] = [];

  for (let y = 0; y < image.length; y++) {
    for (let x = 0; x < image[y].length; x++) {
      flattenedArray.push(image[y][x]);
    }
  }

  return flattenedArray;
}

// Exports
export class MockInteractiveImageSegmenter
  implements InteractiveImageSegmenter
{
  currentMask: Array<number> | null = null;

  segmentImage(input: InteractiveImageSegmenterInput) {
    const image = input.image;
    const w = image.naturalWidth;
    const h = image.naturalHeight;

    if (!this.currentMask) {
      this.currentMask = new Array(w * h);
    }
    this.currentMask.fill(0);

    if (input.points) {
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
    }

    if (input.box) {
      if (this.currentMask) {
        const xstart = Math.round(
          Math.min(input.box.x, input.box.x + input.box.width)
        );
        const width = Math.round(Math.abs(input.box.width));
        const ystart = Math.round(
          Math.min(input.box.y, input.box.y + input.box.height)
        );
        const height = Math.round(Math.abs(input.box.height));
        for (let i = xstart; i < xstart + width; i++) {
          for (let j = ystart; j < ystart + height; j++) {
            this.currentMask[i + j * w] = 1;
          }
        }
      }
    }

    const maskRLE = mask_utils.maskDataToFortranArrayToRle(
      this.currentMask,
      h,
      w
    );
    //console.log(maskRLE)
    const maskPolygons = mask_utils.generatePolygonSegments(maskRLE, h);
    //console.log(maskPolygons);
    const masksSVG = mask_utils.convertSegmentsToSVG(maskPolygons);
    //console.log(masksSVG);
    //console.log(masksSVG.length);
    return Promise.resolve({ masksImageSVG: masksSVG, rle:null });
  }

  reset() {
    this.currentMask = null;
    console.log("Reset Mock Segmenter");
  }
}
