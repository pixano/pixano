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

/**
 * Converts mask array into RLE array using the fortran array
 * format where rows and columns are transposed. This is the
 * format used by the COCO API and is expected by the mask tracer.
 * @param {Array<number>} input
 * @param {number} nrows
 * @param {number} ncols
 * @returns array of integers
 */
export function maskDataToFortranArrayToRle(
  input: any,
  nrows: number,
  ncols: number
): Array<number> {
  const result: Array<number> = [];
  let count = 0;
  let bit = false;
  for (let c = 0; c < ncols; c++) {
    for (let r = 0; r < nrows; r++) {
      var i = c + r * ncols;
      if (i < input.length) {
        const filled = input[i] > 0.0;
        if (filled !== bit) {
          result.push(count);
          bit = !bit;
          count = 1;
        } else count++;
      }
    }
  }
  if (count > 0) result.push(count);
  return result;
}

export function arrayToImageData(
  inputArray: any,
  width: number,
  height: number,
  threshold: number = 0.0
) {
  const [r, g, b, a] = [0, 114, 189, 255];
  const arr = new Uint8ClampedArray(4 * width * height).fill(0);
  for (let i = 0; i < inputArray.length; i++) {
    if (inputArray[i] > threshold) {
      arr[4 * i + 0] = r;
      arr[4 * i + 1] = g;
      arr[4 * i + 2] = b;
      arr[4 * i + 3] = a;
    }
  }
  return new ImageData(arr, height, width);
}

// Use a Canvas element to produce an image from ImageData
export function imageDataToImage(imageData: ImageData) {
  const canvas = imageDataToCanvas(imageData);
  const image = new Image();
  image.src = canvas.toDataURL();
  return image;
}

// Canvas elements can be created from ImageData
export function imageDataToCanvas(imageData: ImageData) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = imageData.width;
  canvas.height = imageData.height;
  ctx?.putImageData(imageData, 0, 0);
  return canvas;
}
