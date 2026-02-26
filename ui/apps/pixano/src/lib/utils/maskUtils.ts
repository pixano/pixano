/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import simplify from "simplify-js";

import { BaseSchema, type MaskSvgPaths } from "$lib/types/dataset";
import type { Point2D } from "$lib/types/geometry";
import type { PolygonVertex } from "$lib/types/shapeTypes";

// ========================================================================================
// Low-level mask-to-polygon algorithms (adapted from segment-anything)
// ========================================================================================

/**
 * Converts mask array into RLE array using the fortran array
 * format where rows and columns are transposed. This is the
 * format used by the COCO API and is expected by the mask tracer.
 * @param {ArrayLike<number>} input
 * @param {number} nrows
 * @param {number} ncols
 * @returns array of integers
 */
export function maskDataToFortranArrayToRle(
  input: ArrayLike<number>,
  nrows: number,
  ncols: number,
): Array<number> {
  const result: Array<number> = [];
  let count = 0;
  let bit = false;
  for (let c = 0; c < ncols; c++) {
    for (let r = 0; r < nrows; r++) {
      const i = c + r * ncols;
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
  inputArray: ArrayLike<number>,
  width: number,
  height: number,
  threshold: number = 0.0,
): ImageData {
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

/**
 * Helper function
 * Converts string representation of point (used as Map key) back into [x, y] array
 * @param {str} point "x y"
 * @returns {Array<number>} [x, y]
 */
function splitPointKey(point: string): Array<number> {
  return point.split(" ").map((a: string) => parseInt(a));
}

/**
 * Used in generatePolygonSegments
 * ------
 * Step 1
 * ------
 * Converts a mask encoded with RLE and converts it into an array of breakpoints per column of the mask.
 *     - Each line starts as 0 by default, and at each breakpoint the bit is flipped
 *     - If a line doesn't exist in the return array, this line is all 0.
 *
 * @param {Array<number>} rleMask
 * @param {number} height (of mask)
 * @returns {Array<Object>} each item is a JS object describing the breakpoints for a line:
 *    {
 *        line {number}: index of line this object describes,
 *        points {Array<number>}: list of pixel indices along line at which bit goes from 0 -> 1 or vice versa
 *    }
 */
function getLineBreakpoints(
  rleMask: string | any[],
  height: number,
): Array<{ line: number; points: any }> {
  const breakpoints = [];
  const currentLine: { line: number; points: any } = { line: -1, points: [] };
  let sum = 0; // sum of pixels seen so far, used to compute breakpoints

  // Helper function to push currentLine data to breakpoints
  const addCurrentLineToBreakpoints = () => {
    if (currentLine.points.length > 0) {
      breakpoints.push({ line: currentLine.line, points: currentLine.points });
      currentLine.points = [];
    }
  };

  // Iterate through every pair of values in rleMask
  for (let i = 1; i < rleMask.length; i += 2) {
    // Get coords of start/end pixels of the filled block
    sum += rleMask[i - 1];
    const y1 = sum % height;
    const x1 = Math.floor(sum / height);

    sum += rleMask[i];
    const y2 = sum % height;
    const x2 = Math.floor(sum / height);

    if (currentLine.line !== x1) {
      addCurrentLineToBreakpoints();
      currentLine.line = x1;
    }
    // Case if the block is just one line
    if (x1 === x2) {
      currentLine.points.push(y1, y2);
      continue;
    }
    // Otherwise, first handle the first line of the block
    currentLine.points.push(y1, height);
    addCurrentLineToBreakpoints();
    currentLine.line = x2;
    // Then handle in-between lines, which are all filled
    for (let x0 = x1 + 1; x0 < x2; x0++) {
      breakpoints.push({ line: x0, points: [0, height] });
    }
    // Lastly, handle the last line of the block
    if (y2 > 0) {
      currentLine.points.push(0, y2);
    }
  }
  // Push any remaining data in currentLine to breakpoints
  addCurrentLineToBreakpoints();

  return breakpoints;
}

/**
 * ------
 * Step 2
 * ------
 * Generates a Map of segments that collectively trace all EDGES within a mask.
 *
 * @param {Array<number>} rleMask
 * @param {number} height (of mask)
 * @returns {Map<string, Set<string>>} Map of all vertices to its adjacent vertices
 *    - key: "x y" string-formatted point
 *    - value: Set of string-formatted points adjacent to key
 */
export function generatePolygonSegments(
  rleMask: Array<number>,
  height: number,
): Map<string, Set<string>> {
  const breakpoints = getLineBreakpoints(rleMask, height);

  // If mask is actually an empty mask, return nothing since there are no edges
  if (breakpoints.length === 0) return new Map();

  // Now, generate the outline as a set of lines using the breakpoints
  const polySegments = new Map(); // maps str points to set of target points
  let lastLine = -1;
  let lastPoints: string | any[] = [];

  // This is a solution optimization that caches horizontal segments so that consecutive
  // straight horizontal segments can be joined into one long segment
  const horizontalSegments = new Map(); // maps y to starting x

  // ------------------
  //  Helper functions
  // ------------------

  // Given two points, format each into a string and add the bidirectional segment to polySegments
  const addToPolySegments = (p1: { x: any; y: any }, p2: { x: any; y: any }) => {
    const p1Str = `${p1.x} ${p1.y}`,
      p2Str = `${p2.x} ${p2.y}`;
    if (!polySegments.has(p1Str)) polySegments.set(p1Str, new Set());
    polySegments.get(p1Str).add(p2Str);
    if (!polySegments.has(p2Str)) polySegments.set(p2Str, new Set());
    polySegments.get(p2Str).add(p1Str);
  };

  // For the horizontal segment optimization:
  //    A horizontal segment can no longer be extended because the end vertex has been connected in a different direction,
  //    so given y and the designated ending x, add the segment to polySegments and remove it from horizontalSegments
  const closeHorizontalSegment = (y: any, x2: number) => {
    // Don't close if x2 is the start vertex, because the segment can still be extended the other way
    if (x2 !== horizontalSegments.get(y)) {
      addToPolySegments({ x: horizontalSegments.get(y), y }, { x: x2, y });
      horizontalSegments.delete(y);
    }
  };

  // Process a segment from (x1, y1) to (x2, y2), handling possible horizontal segment and straightening optimizations
  const addSegment = (x1: number, y1: any, x2: number, y2: any) => {
    // If the segment is horizontal, add it to the intermediate horizontalSegments map instead
    if (y1 === y2) {
      if (!horizontalSegments.has(y1)) horizontalSegments.set(y1, x1);
      return;
    }

    // Otherwise, we check both vertices to see if they connect to any horizontal segments, and if so we close them
    // "Straightening" solution optimization:
    //    In the case where both of the following are true:
    //        - this segment (x1, y1) to (x2, y2) is diagonal (note |x1 - x2| <= 1)
    //        - it closes at least one horizontal segment
    //    Then we should adjust one x coordinate by 1 pixel to make sure right angles are correctly drawn
    let canStraighten = false;
    const maxX = Math.max(x1, x2); // If we do straighten, align both vertices to the right
    if (horizontalSegments.has(y1)) {
      closeHorizontalSegment(y1, maxX);
      canStraighten = true;
    }
    if (horizontalSegments.has(y2)) {
      closeHorizontalSegment(y2, maxX);
      canStraighten = true;
    }
    // Add line, setting x to maxX if a horizontal segment has been closed
    if (canStraighten) addToPolySegments({ x: maxX, y: y1 }, { x: maxX, y: y2 });
    else addToPolySegments({ x: x1, y: y1 }, { x: x2, y: y2 });
  };

  // This function handles the case where a line with a nonzero number of pixels is followed by an empty line,
  //    so we can add edges to close any incomplete polygons.
  // We trace the right edge of the pixel (prevLine + 1) instead of left to ensure the area of the polygon is nonzero
  const closePreviousLine = (prevLine: number, prevPoints: string | any[]) => {
    // For every breakpoint in the previous line, add a horizontal segment up to the right edge of the line
    for (const y of prevPoints) addSegment(prevLine, y, prevLine + 1, y);
    // Then connect every pair of breakpoints along the current line to close polygons
    for (let i = 1; i < prevPoints.length; i += 2) {
      addSegment(prevLine + 1, prevPoints[i - 1], prevLine + 1, prevPoints[i]);
    }
  };

  // -----------
  //  Main loop
  // -----------
  // Iterate through each line of the breakpoints array and connect breakpoints as necessary to generate segments

  for (const { line, points } of breakpoints) {
    // If the new line isn't the one directly after the previous one, close existing polygons and reset state
    if (line !== lastLine + 1) {
      closePreviousLine(lastLine, lastPoints);
      lastLine = line - 1;
      lastPoints = [];
    }
    // We want to iterate through breakpoints in both lines in order of increasing y value
    // Find the first breakpoint
    let x1: number = lastPoints.length && lastPoints[0] <= points[0] ? lastLine : line;
    let y1: number = x1 === lastLine ? lastPoints[0] : points[0];
    // Keep a pointer for each line
    let lastLineIndex = x1 === lastLine ? 1 : 0;
    let newLineIndex = x1 === lastLine ? 0 : 1;
    // Flag to track if this is an odd or even breakpoint (we want to handle breakpoints two at a time)
    let odd = true;
    while (lastLineIndex < lastPoints.length || newLineIndex < points.length) {
      // Get next breakpoint by comparing values at pointer for both lines
      let x2: number, y2: number;
      if (lastLineIndex === lastPoints.length || points[newLineIndex] < lastPoints[lastLineIndex]) {
        x2 = line;
        y2 = points[newLineIndex];
        newLineIndex++;
      } else {
        x2 = lastLine;
        y2 = lastPoints[lastLineIndex];
        lastLineIndex++;
      }
      // If previous breakpoint was odd, then we now have a pair and should connect them
      if (odd) {
        if (x1 === lastLine && x2 === lastLine) {
          // If both breakpoints are on the previous line, we are closing a polygon and should
          // do so on the right-most edge to guarantee a non-zero area (see closePreviousLine)
          addSegment(lastLine, y1, line, y1);
          addSegment(lastLine, y2, line, y2);
          addSegment(line, y1, line, y2);
        } else {
          // Otherwise just connect the two points with a segment
          addSegment(x1, y1, x2, y2);
        }
      }
      odd = !odd;
      x1 = x2;
      y1 = y2;
    }

    // Update last line and points
    lastLine = line;
    lastPoints = points;
  }
  // Close any remaining polygons after the last line
  closePreviousLine(lastLine, lastPoints);

  // Reinitialize the map with keys in sorted order by (x, y)
  const sortedSegments = new Map(
    [...polySegments].sort((a: Array<string>, b: Array<string>) => {
      const [x1, y1] = splitPointKey(a[0]);
      const [x2, y2] = splitPointKey(b[0]);
      if (x1 === x2) return y1 - y2;
      return x1 - x2;
    }),
  );

  return sortedSegments;
}

export function generateLineCoordinates(rleMask: number[], height: number): number[] {
  const breakpoints = getLineBreakpoints(rleMask, height);
  const mappedBreakpoints: { x: number; y: number }[] = breakpoints.map((point) => ({
    x: point.points[0] as number,
    y: point.points[1] as number,
  }));
  const flatBreakpoints = mappedBreakpoints.reduce((acc, val) => {
    acc.push(val.y, val.x);
    return acc;
  }, [] as number[]);

  return flatBreakpoints;
}

export function generatePolygonCoordinates(rleMask: Array<number>, height: number): number[] {
  const breakpoints = getLineBreakpoints(rleMask, height);

  // If mask is actually an empty mask, return nothing since there are no edges
  if (breakpoints.length === 0) return [];

  // Now, generate the outline as a set of lines using the breakpoints
  const polySegments = new Map(); // maps str points to set of target points
  let lastLine = -1;
  let lastPoints: string | any[] = [];

  // This is a solution optimization that caches horizontal segments so that consecutive
  // straight horizontal segments can be joined into one long segment
  const horizontalSegments = new Map(); // maps y to starting x

  // ------------------
  //  Helper functions
  // ------------------

  // Given two points, format each into a string and add the bidirectional segment to polySegments
  const addToPolySegments = (p1: { x: any; y: any }, p2: { x: any; y: any }) => {
    const p1Str = `${p1.x} ${p1.y}`,
      p2Str = `${p2.x} ${p2.y}`;
    if (!polySegments.has(p1Str)) polySegments.set(p1Str, new Set());
    polySegments.get(p1Str).add(p2Str);
    if (!polySegments.has(p2Str)) polySegments.set(p2Str, new Set());
    polySegments.get(p2Str).add(p1Str);
  };

  // For the horizontal segment optimization:
  //    A horizontal segment can no longer be extended because the end vertex has been connected in a different direction,
  //    so given y and the designated ending x, add the segment to polySegments and remove it from horizontalSegments
  const closeHorizontalSegment = (y: any, x2: number) => {
    // Don't close if x2 is the start vertex, because the segment can still be extended the other way
    if (x2 !== horizontalSegments.get(y)) {
      addToPolySegments({ x: horizontalSegments.get(y), y }, { x: x2, y });
      horizontalSegments.delete(y);
    }
  };

  // Process a segment from (x1, y1) to (x2, y2), handling possible horizontal segment and straightening optimizations
  const addSegment = (x1: number, y1: any, x2: number, y2: any) => {
    // If the segment is horizontal, add it to the intermediate horizontalSegments map instead
    if (y1 === y2) {
      if (!horizontalSegments.has(y1)) horizontalSegments.set(y1, x1);
      return;
    }

    // Otherwise, we check both vertices to see if they connect to any horizontal segments, and if so we close them
    // "Straightening" solution optimization:
    //    In the case where both of the following are true:
    //        - this segment (x1, y1) to (x2, y2) is diagonal (note |x1 - x2| <= 1)
    //        - it closes at least one horizontal segment
    //    Then we should adjust one x coordinate by 1 pixel to make sure right angles are correctly drawn
    let canStraighten = false;
    const maxX = Math.max(x1, x2); // If we do straighten, align both vertices to the right
    if (horizontalSegments.has(y1)) {
      closeHorizontalSegment(y1, maxX);
      canStraighten = true;
    }
    if (horizontalSegments.has(y2)) {
      closeHorizontalSegment(y2, maxX);
      canStraighten = true;
    }
    // Add line, setting x to maxX if a horizontal segment has been closed
    if (canStraighten) addToPolySegments({ x: maxX, y: y1 }, { x: maxX, y: y2 });
    else addToPolySegments({ x: x1, y: y1 }, { x: x2, y: y2 });
  };

  // This function handles the case where a line with a nonzero number of pixels is followed by an empty line,
  //    so we can add edges to close any incomplete polygons.
  // We trace the right edge of the pixel (prevLine + 1) instead of left to ensure the area of the polygon is nonzero
  const closePreviousLine = (prevLine: number, prevPoints: string | any[]) => {
    // For every breakpoint in the previous line, add a horizontal segment up to the right edge of the line
    for (const y of prevPoints) addSegment(prevLine, y, prevLine + 1, y);
    // Then connect every pair of breakpoints along the current line to close polygons
    for (let i = 1; i < prevPoints.length; i += 2) {
      addSegment(prevLine + 1, prevPoints[i - 1], prevLine + 1, prevPoints[i]);
    }
  };

  // -----------
  //  Main loop
  // -----------
  // Iterate through each line of the breakpoints array and connect breakpoints as necessary to generate segments

  for (const { line, points } of breakpoints) {
    // If the new line isn't the one directly after the previous one, close existing polygons and reset state
    // if (line !== lastLine + 1) {
    //   closePreviousLine(lastLine, lastPoints);
    //   lastLine = line - 1;
    //   lastPoints = [];
    // }
    // We want to iterate through breakpoints in both lines in order of increasing y value
    // Find the first breakpoint
    let x1: number = lastPoints.length && lastPoints[0] <= points[0] ? lastLine : line;
    let y1: number = x1 === lastLine ? lastPoints[0] : points[0];
    // Keep a pointer for each line
    let lastLineIndex = x1 === lastLine ? 1 : 0;
    let newLineIndex = x1 === lastLine ? 0 : 1;
    // Flag to track if this is an odd or even breakpoint (we want to handle breakpoints two at a time)
    let odd = true;
    while (lastLineIndex < lastPoints.length || newLineIndex < points.length) {
      // Get next breakpoint by comparing values at pointer for both lines
      let x2: number, y2: number;
      if (lastLineIndex === lastPoints.length || points[newLineIndex] < lastPoints[lastLineIndex]) {
        x2 = line;
        y2 = points[newLineIndex];
        newLineIndex++;
      } else {
        x2 = lastLine;
        y2 = lastPoints[lastLineIndex];
        lastLineIndex++;
      }
      // If previous breakpoint was odd, then we now have a pair and should connect them
      if (odd) {
        if (x1 === lastLine && x2 === lastLine) {
          // If both breakpoints are on the previous line, we are closing a polygon and should
          // do so on the right-most edge to guarantee a non-zero area (see closePreviousLine)
          addSegment(lastLine, y1, line, y1);
          addSegment(lastLine, y2, line, y2);
          addSegment(line, y1, line, y2);
        } else {
          // Otherwise just connect the two points with a segment
          addSegment(x1, y1, x2, y2);
        }
      }
      odd = !odd;
      x1 = x2;
      y1 = y2;
    }

    // Update last line and points
    lastLine = line;
    lastPoints = points;
  }
  // Close any remaining polygons after the last line
  // closePreviousLine(lastLine, lastPoints);

  // Reinitialize the map with keys in sorted order by (x, y)
  const sortedSegments = new Map(
    [...polySegments].sort((a: Array<string>, b: Array<string>) => {
      const [x1, y1] = splitPointKey(a[0]);
      const [x2, y2] = splitPointKey(b[0]);
      if (x1 === x2) return y1 - y2;
      return x1 - x2;
    }),
  );

  let coords: number[] = [];
  sortedSegments.forEach((_, key) => {
    const [x, y] = splitPointKey(key);
    coords = [...coords, x, y];
  });

  return coords;
}

/**
 * ------
 * Step 3
 * ------
 * Converts Map of segments from generatePolygonSegments into closed SVG paths combined into one string,
 * where nested paths alternate direction so holes are correctly rendered using the nonzero fill rule.
 * @param {Map<string, Set<string>>} polySegments output of generatePolygonSegments
 * @returns {Array<string>} SVG data string for display
 */
export function convertSegmentsToSVG(polySegments: Map<string, Set<string>>): Array<string> {
  // 1. Generate the closed polygon paths (as lists of points) in order from outermost to innermost
  const paths: Array<Array<Array<number>>> = [];
  while (polySegments.size) {
    // Pick the outermost vertex from the remaining set (smallest (x, y))
    let [point, targets]: [string, Set<string>] = polySegments.entries().next().value!;
    const firstPoint = point;
    const path = [splitPointKey(firstPoint)];
    // Repeatedly pick the next adjacent vertex and add it to the path until the path is closed
    let nextPoint: string = "";
    while (nextPoint !== firstPoint) {
      nextPoint = targets.values().next().value!;
      // TODO
      if (nextPoint === undefined) break;
      path.push(splitPointKey(nextPoint));
      // Remove used edges and delete the point from polySegments entirely if it has no more edges left
      targets.delete(nextPoint);
      if (targets.size === 0) polySegments.delete(point);
      // Do the same for the bidirectional edge
      const nextPointTargets = polySegments.get(nextPoint);
      nextPointTargets?.delete(point);
      // Move to the next set of edges, unless it is empty in which case break since we've completed a loop
      if (nextPointTargets?.size === 0) {
        polySegments.delete(nextPoint);
        break;
      } else {
        point = nextPoint;
        if (nextPointTargets) targets = nextPointTargets;
      }
    }
    paths.push(path);
  }

  // 2. Compute desired direction for each path, flip if necessary, then convert to SVG string
  const renderedPaths: Array<Path2D> = [];
  const svgStrings = [];

  // We use a canvas element to draw the paths and check isPointInPath to determine wanted direction
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  for (const path of paths) {
    // Count how many other paths a point contained inside this path is contained within
    //  if odd number: should be clockwise, even number: should be counter-clockwise
    let shouldBeClockwise = false;
    const [sampleX, sampleY]: Array<number> = path[0];
    for (const otherPath of renderedPaths) {
      if (ctx?.isPointInPath(otherPath, sampleX + 0.5, sampleY + 0.5))
        shouldBeClockwise = !shouldBeClockwise;
    }
    // All paths are default counter-clockwise based on how the segments were generated,
    //    so reverse the points in the path if it is supposed to be clockwise
    if (shouldBeClockwise) path.reverse();

    // Build the SVG data string for this path
    const stringPoints = path
      .slice(1)
      .map(([x, y]) => `${x} ${y}`)
      .join(" ");
    const svgStr = `M${path[0][0]} ${path[0][1]} L` + stringPoints;
    svgStrings.push(svgStr); // Add to final SVG string return value

    // Add a new Path2D to the canvas to be able to call isPointInPath for the remaining paths
    const pathObj = new Path2D(svgStr);
    ctx?.fill(pathObj);
    renderedPaths.push(pathObj);
  }

  return svgStrings;
}

// ========================================================================================
// Higher-level SVG processing, RLE string encoding
// ========================================================================================

export const parseSvgPath = (svgPath: string): PolygonVertex[] => {
  const regex = /([ML]?)\s*([\d.]+)\s+([\d.]+)/g;
  let match: RegExpExecArray | null;
  let result: Point2D[] = [];
  while ((match = regex.exec(svgPath)) !== null) {
    const [, , x, y] = match;
    result.push({ x: parseFloat(x), y: parseFloat(y) });
  }
  result = simplify(result, 0, true);
  return result.map((r, i) => ({ ...r, id: i }));
};

export const convertPointToSvg = (points: PolygonVertex[]) =>
  points.reduce((acc, val, i) => {
    if (i === 0) {
      return `M${val.x} ${val.y}`;
    }
    if (i === 1) {
      return `${acc} L${val.x} ${val.y}`;
    }
    return `${acc} ${val.x} ${val.y}`;
  }, "");

export const hexToRGBA = (hex: string, alpha: number) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

//utility functions to extract coords from SVG
//works only with SVG format "Mx0 y0 Lx1 y1 ... xn yn"
// --> format generated by convertSegmentsToSVG
export function m_part(svg: string) {
  const splits = svg.split(" ");
  const x = splits[0].slice(1); //remove "M"
  return { x: parseInt(x), y: parseInt(splits[1]) };
}
export function l_part(svg: string) {
  const splits = svg.split(" ");
  const x0 = splits[2]?.slice(1); //remove "L"
  const res = [{ x: parseInt(x0), y: parseInt(splits[3]) }];
  for (let i = 4; i < splits.length; i += 2) {
    res.push({
      x: parseInt(splits[i]),
      y: parseInt(splits[i + 1]),
    });
  }
  return res;
}

// Fonction de conversion RLE vers chaîne de caractères
export function rleToString(cnts: number[]): string {
  let result = "";
  for (let i = 0; i < cnts.length; i++) {
    let x = cnts[i];
    // Si c'est au-delà du deuxième élément, on applique la différence avec cnts[i-2]
    if (i > 2) {
      x -= cnts[i - 2];
    }
    let more = true;
    // Encodage en utilisant 6 bits par caractère
    while (more) {
      let c = x & 0x1f; // Extraire les 5 bits de poids faible
      x >>= 5; // Décaler les bits de 5 positions vers la droite

      // Déterminer s'il y a plus de chiffres à traiter
      more = c & 0x10 ? x !== -1 : x !== 0;
      if (more) {
        c |= 0x20; // Ajouter un indicateur de continuation
      }
      // Convertir en caractère ASCII (48-111)
      result += String.fromCharCode(c + 48);
    }
  }
  return result;
}

//translation of pycocotools rleFrString from python to Typescript
export function rleFrString(s: string): number[] {
  let p = 0; // Pointer to traverse string
  const cnts: number[] = [];

  // Step 1: Decode the string s
  while (p < s.length) {
    let x = 0;
    let k = 0;
    let more = true;

    while (more) {
      const c = s.charCodeAt(p) - 48; // Decode character to integer
      x |= (c & 0x1f) << (5 * k); // Take the first 5 bits of c
      more = (c & 0x20) !== 0; // Check if there is more to decode
      p++;
      k++;
      if (!more && c & 0x10) {
        x |= -1 << (5 * k); // If negative, handle sign extension
      }
    }
    // Step 2: Handle cumulative addition
    if (cnts.length > 2) {
      x += cnts[cnts.length - 2]; // Apply shift for previous counts
    }
    cnts.push(x); // Add decoded value to cnts array
  }
  return cnts;
}

// Function to parse SVG path (as provided in the previous response)
function svgPathToBitmap(svgPath: string | string[], width: number, height: number): number[] {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");

  // Draw the SVG path on the canvas
  if (context) {
    context.clearRect(0, 0, width, height);
    context.fillStyle = "black";
    if (Array.isArray(svgPath)) {
      const combined = new Path2D();
      for (const path of svgPath) {
        combined.addPath(new Path2D(path));
      }
      context.fill(combined, "evenodd");
    } else {
      context.fill(new Path2D(svgPath), "evenodd");
    }
  }

  // Get the image data from the canvas
  const imageData = context
    ? context.getImageData(0, 0, width, height).data
    : new Uint8ClampedArray(width * height * 4);
  // Convert the image data to a binary bitmap
  const bitmap: number[] = [];
  for (let i = 0; i < imageData.length; i += 4) {
    // Convert RGBA to binary (considering only the alpha channel)
    bitmap.push(imageData[i + 3] === 0 ? 0 : 1);
  }
  return bitmap;
}

function rleEncode(bitmap: number[]): number[] {
  const counts: number[] = [];
  let count = 1;
  for (let i = 1; i < bitmap.length; i++) {
    if (bitmap[i] === bitmap[i - 1]) {
      count++;
    } else {
      counts.push(count);
      count = 1;
    }
  }
  // Handle the last sequence
  counts.push(count);
  return counts;
}

function reshapeArray(array: number[], rows: number, cols: number): number[] {
  if (array.length !== rows * cols) {
    throw new Error("Can't reshape with length != cols*rows");
  }
  const reshapedArray: number[] = [];
  for (let col = 0; col < cols; col++) {
    for (let row = 0; row < rows; row++) {
      reshapedArray.push(array[row * cols + col]);
    }
  }
  return reshapedArray;
}

export function runLengthEncode(svg: MaskSvgPaths, imageWidth: number, imageHeight: number): number[] {
  let bitmap = svgPathToBitmap(svg, imageWidth, imageHeight);
  bitmap = reshapeArray(bitmap, imageHeight, imageWidth);
  return rleEncode(bitmap);
}

export function getBoundingBoxFromMaskSvgPaths(svg: MaskSvgPaths): {
  x: number;
  y: number;
  width: number;
  height: number;
} | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const path of svg) {
    const start = m_part(path);
    minX = Math.min(minX, start.x);
    minY = Math.min(minY, start.y);
    maxX = Math.max(maxX, start.x);
    maxY = Math.max(maxY, start.y);

    const l_pts = l_part(path);
    for (const pt of l_pts) {
      minX = Math.min(minX, pt.x);
      minY = Math.min(minY, pt.y);
      maxX = Math.max(maxX, pt.x);
      maxY = Math.max(maxY, pt.y);
    }
  }

  if (minX === Infinity) return null;

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

/**
 * Check if an annotation is a Mask stored with polygon geometry mode.
 */
export function isRawPolygonMask(annotation: { table_info: { base_schema: string }; data: { inference_metadata?: Record<string, unknown> } }): boolean {
  if (annotation.table_info.base_schema !== BaseSchema.Mask) return false;
  const metadata = annotation.data.inference_metadata as Record<string, unknown> | undefined;
  return metadata?.geometry_mode === "polygon";
}

export function isPolygonSvgMetadata(
  metadata: Record<string, unknown>,
): metadata is Record<string, unknown> & { polygon_svg: string[] } {
  const svg = metadata.polygon_svg;
  return (
    metadata.geometry_mode === "polygon" &&
    Array.isArray(svg) &&
    svg.every((value) => typeof value === "string")
  );
}

export function isPolygonPointsMetadata(
  metadata: Record<string, unknown>,
): metadata is Record<string, unknown> & { polygon_points: PolygonVertex[][] } {
  const pts = metadata.polygon_points;
  return (
    metadata.geometry_mode === "polygon" &&
    Array.isArray(pts) &&
    pts.every(
      (polygon) =>
        Array.isArray(polygon) &&
        polygon.every(
          (point) =>
            typeof point === "object" && point !== null && "x" in point && "y" in point && "id" in point,
        ),
    )
  );
}

export function generateSvgFromMaskRle(counts: number[], size: number[]): string[] {
  const maskPoly = generatePolygonSegments(counts, size[0]);
  return convertSegmentsToSVG(maskPoly);
}
