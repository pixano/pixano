/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const equalizeHistogram = (imageData: ImageData) => {
  const { width, height, data } = imageData;
  const nPixels = width * height;

  // Create histograms for each channel
  const histR: number[] = new Array(256).fill(0) as number[];
  const histG: number[] = new Array(256).fill(0) as number[];
  const histB: number[] = new Array(256).fill(0) as number[];

  // Calculate histograms
  for (let i = 0; i < nPixels * 4; i += 4) {
    histR[data[i]]++;
    histG[data[i + 1]]++;
    histB[data[i + 2]]++;
  }

  // Calculate cumulative distribution function (CDF) for each channel
  const cdfR: number[] = new Array(256).fill(0) as number[];
  const cdfG: number[] = new Array(256).fill(0) as number[];
  const cdfB: number[] = new Array(256).fill(0) as number[];

  cdfR[0] = histR[0];
  cdfG[0] = histG[0];
  cdfB[0] = histB[0];

  for (let i = 1; i < 256; i++) {
    cdfR[i] = cdfR[i - 1] + histR[i];
    cdfG[i] = cdfG[i - 1] + histG[i];
    cdfB[i] = cdfB[i - 1] + histB[i];
  }

  // Normalize the CDF
  const cdfRMin = cdfR.find((value) => value > 0);
  const cdfGMin = cdfG.find((value) => value > 0);
  const cdfBMin = cdfB.find((value) => value > 0);

  for (let i = 0; i < 256; i++) {
    cdfR[i] = ((cdfR[i] - cdfRMin) / (nPixels - cdfRMin)) * 255;
    cdfG[i] = ((cdfG[i] - cdfGMin) / (nPixels - cdfGMin)) * 255;
    cdfB[i] = ((cdfB[i] - cdfBMin) / (nPixels - cdfBMin)) * 255;
  }

  // Apply equalization to the image data
  for (let i = 0; i < nPixels * 4; i += 4) {
    data[i] = Math.round(cdfR[data[i]]);
    data[i + 1] = Math.round(cdfG[data[i + 1]]);
    data[i + 2] = Math.round(cdfB[data[i + 2]]);
  }
};
