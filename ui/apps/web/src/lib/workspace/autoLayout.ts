/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { WorkspacePreset } from "$lib/extensions/types";
import type { ViewComposition } from "$lib/utils/viewComposition";

const GRID_COLS = 12;
const MIN_W = 2;
const MIN_H = 2;
const IMG_H = 3; // row height for each camera image
const PC_MIN_W = 3;

/**
 * Produce a WorkspacePreset from a view composition.
 *
 * Layout rules:
 * - Mixed (point clouds + images): point clouds fill the left half, camera
 *   images are arranged in a square grid on the right half.
 * - Point clouds only: evenly divided across the full width.
 * - Images only: arranged in a square grid across the full width.
 *
 * Each widget carries `options.logicalName` so the widget component knows
 * which view to fetch from the API.
 */
export function generateLayoutFromViews(composition: ViewComposition): WorkspacePreset {
  const widgets: WorkspacePreset["widgets"] = [];
  const { images, pointClouds } = composition;

  const hasPCs = pointClouds.length > 0;
  const hasImages = images.length > 0;

  if (hasPCs && hasImages) {
    // Divide the grid: left half for point clouds, right half for images.
    const imgCols = Math.ceil(Math.sqrt(images.length));
    const imgRows = Math.ceil(images.length / imgCols);
    const totalH = imgRows * IMG_H;

    const pcAreaW = Math.max(PC_MIN_W * pointClouds.length, Math.floor(GRID_COLS / 2));
    const imgAreaW = GRID_COLS - pcAreaW;
    const pcW = Math.max(PC_MIN_W, Math.floor(pcAreaW / pointClouds.length));
    const imgW = Math.max(MIN_W, Math.floor(imgAreaW / imgCols));

    pointClouds.forEach((logicalName, i) => {
      widgets.push({
        extensionName: "point-cloud",
        title: logicalName,
        layout: { x: i * pcW, y: 0, w: pcW, h: totalH, minW: PC_MIN_W, minH: MIN_H },
        options: { logicalName },
        data: {},
      });
    });

    images.forEach((logicalName, i) => {
      const col = i % imgCols;
      const row = Math.floor(i / imgCols);
      widgets.push({
        extensionName: "image",
        title: logicalName,
        layout: {
          x: pcAreaW + col * imgW,
          y: row * IMG_H,
          w: imgW,
          h: IMG_H,
          minW: MIN_W,
          minH: MIN_H,
        },
        options: { logicalName },
        data: {},
      });
    });
  } else if (hasPCs) {
    const pcW = Math.max(PC_MIN_W, Math.floor(GRID_COLS / pointClouds.length));
    pointClouds.forEach((logicalName, i) => {
      widgets.push({
        extensionName: "point-cloud",
        title: logicalName,
        layout: { x: i * pcW, y: 0, w: pcW, h: 6, minW: PC_MIN_W, minH: MIN_H },
        options: { logicalName },
        data: {},
      });
    });
  } else if (hasImages) {
    const imgCols = Math.max(1, Math.ceil(Math.sqrt(images.length)));
    const imgW = Math.max(MIN_W, Math.floor(GRID_COLS / imgCols));
    images.forEach((logicalName, i) => {
      const col = i % imgCols;
      const row = Math.floor(i / imgCols);
      widgets.push({
        extensionName: "image",
        title: logicalName,
        layout: { x: col * imgW, y: row * 5, w: imgW, h: 5, minW: MIN_W, minH: MIN_H },
        options: { logicalName },
        data: {},
      });
    });
  }

  return { name: "Auto", widgets };
}
