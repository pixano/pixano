import type { BreakPoint, EditShape, ItemBBox, ItemObject, Tracklet } from "@pixano/core";

export const getCurrentImageTime = (imageIndex: number, videoSpeed: number) => {
  const currentTimestamp = imageIndex * videoSpeed;
  const minutes = Math.floor(currentTimestamp / 60000);
  const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
  return `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
};

export const getImageIndexFromMouseMove = (
  event: MouseEvent,
  node: HTMLButtonElement,
  length: number,
) => {
  const parentBounding = node.parentElement?.getBoundingClientRect();
  let left = event.clientX - (parentBounding?.left || 0);
  if (left < 0) left = 0;
  const max = node.parentElement?.offsetWidth || left;
  if (left > max) left = max;
  const index = Math.floor((left / max) * length) - 1;
  return index < 0 ? 0 : index;
};

export const linearInterpolation = (track: Tracklet[], imageIndex: number) => {
  const currentTracklet = track.find(
    (tracklet) => tracklet.start <= imageIndex && tracklet.end >= imageIndex,
  );
  if (!currentTracklet) return null;
  let endIndex = currentTracklet.keyBoxes.findIndex((box) => box.frameIndex > imageIndex);
  endIndex = endIndex < 0 ? currentTracklet.keyBoxes.length - 1 : endIndex;
  const start = currentTracklet.keyBoxes[endIndex - 1] || currentTracklet.keyBoxes[0];
  const end = currentTracklet.keyBoxes[endIndex];
  const [startX, startY] = start.coords;
  const [endX, endY] = end.coords;

  const xInterpolation = (endX - startX) / (end.frameIndex - start?.frameIndex);
  const yInterpolation = (endY - startY) / (end.frameIndex - start?.frameIndex);
  const x = startX + xInterpolation * (imageIndex - start.frameIndex);
  const y = startY + yInterpolation * (imageIndex - start.frameIndex);
  return [x, y];
};

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  box: ItemBBox,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    if (objectId === object.id && object.datasetItemType === "video") {
      object.track = object.track
        .map((tracklet) => {
          if (tracklet.start <= box.frameIndex && tracklet.end >= box.frameIndex) {
            tracklet.keyBoxes = tracklet.keyBoxes.filter(
              (keyBox) => keyBox.frameIndex !== box.frameIndex,
            );
            tracklet.start = tracklet.keyBoxes[0].frameIndex;
            tracklet.end = tracklet.keyBoxes[tracklet.keyBoxes.length - 1].frameIndex;
          }
          return tracklet;
        })
        .filter((tracklet) => tracklet.keyBoxes.length > 1);
    }
    return object;
  });

export const editBreakPointInInterval = (
  objects: ItemObject[],
  boxBeingEdited: ItemBBox,
  shape: EditShape,
) =>
  objects.map((object) => {
    if (
      shape.type === "rectangle" &&
      object.id === shape.shapeId &&
      object.datasetItemType === "video"
    ) {
      object.track = object.track.map((tracklet) => {
        if (
          tracklet.start <= boxBeingEdited.frameIndex &&
          tracklet.end >= boxBeingEdited.frameIndex
        ) {
          tracklet.keyBoxes = tracklet.keyBoxes.map((keyBox) => {
            if (keyBox.frameIndex === boxBeingEdited.frameIndex) {
              keyBox.coords = shape.coords;
              object.displayedBox.coords = shape.coords;
              return keyBox;
            }
            return keyBox;
          });
        }
        return tracklet;
      });
    }
    return object;
  });

// const createNewInterval = (
//   intervals: BreakPointInterval[],
//   frameIndex: number,
//   lastFrameIndex: number,
//   breakPoint: BreakPoint,
// ) => {
//   let nextIntervalStart = intervals.find((i) => i.start > frameIndex)?.start;
//   nextIntervalStart = nextIntervalStart ? nextIntervalStart - 1 : lastFrameIndex;
//   return {
//     start: frameIndex,
//     end: nextIntervalStart,
//     breakPoints: [
//       {
//         frameIndex,
//         x: breakPoint.x,
//         y: breakPoint.y,
//       },
//       {
//         frameIndex: nextIntervalStart,
//         x: breakPoint.x,
//         y: breakPoint.y,
//       },
//     ],
//   } as BreakPointInterval;
// };

// const addBreakPointToInterval = (
//   intervals: BreakPointInterval[],
//   breakpointInterval: BreakPointInterval,
//   breakPoint: BreakPoint,
// ) =>
//   intervals.map((interval) => {
//     if (interval.start === breakpointInterval.start && interval.end === breakpointInterval.end) {
//       interval.breakPoints.push(breakPoint);
//       interval.breakPoints.sort((a, b) => a.frameIndex - b.frameIndex);
//       interval.start = interval.breakPoints[0].frameIndex;
//       interval.end = interval.breakPoints.at(-1)?.frameIndex || interval.start;
//     }
//     return interval;
//   });

export const addBreakPointInInterval = (
  objects: ItemObject[],
  breakPoint: BreakPoint,
  objectId: string,
  // frameIndex: number,
  // lastFrameIndex: number,
) => {
  return objects.map((object) => {
    if (objectId !== object.id || !object.bbox) return object;
    // if (!object.bbox.breakPointsIntervals) {
    //   object.bbox.breakPointsIntervals = [];
    // }
    // const breakpointInterval = object.bbox.breakPointsIntervals.find(
    //   (i) => i.start <= frameIndex && i.end >= frameIndex,
    // );
    // if (!breakpointInterval) {
    //   const newInterval = createNewInterval(
    //     object.bbox.breakPointsIntervals,
    //     frameIndex,
    //     lastFrameIndex,
    //     breakPoint,
    //   );
    //   object.bbox.breakPointsIntervals.push(newInterval);
    // } else {
    //   object.bbox.breakPointsIntervals = addBreakPointToInterval(
    //     object.bbox.breakPointsIntervals,
    //     breakpointInterval,
    //     breakPoint,
    //   );
    // }
    return object;
  });
};

export const findNeighbors = (
  track: Tracklet[],
  currentTracklet: Tracklet,
  frameIndex: ItemBBox["frameIndex"],
  lastFrameIndex: number,
): [number, number] => {
  const currentIntervalIndex = track.findIndex(
    (int) => int.start === currentTracklet.start && int.end === currentTracklet.end,
  );
  if (currentIntervalIndex < 0) return [0, 0];
  const prevTracklet = track[currentIntervalIndex - 1];
  let prevNeighbor = currentTracklet.keyBoxes.find(
    (box) => box.frameIndex < frameIndex,
  )?.frameIndex;
  if (!prevNeighbor && prevTracklet) {
    prevNeighbor = prevTracklet.keyBoxes[prevTracklet.keyBoxes.length - 1]?.frameIndex;
  }
  prevNeighbor = prevNeighbor || 0;

  let nextNeighbor = currentTracklet.keyBoxes.find(
    (box) => box.frameIndex > frameIndex,
  )?.frameIndex;
  const nextTracklet = track[currentIntervalIndex + 1];
  if (!nextNeighbor && nextTracklet) {
    nextNeighbor = nextTracklet.keyBoxes[0]?.frameIndex;
  }
  nextNeighbor = nextNeighbor || lastFrameIndex;

  return [prevNeighbor, nextNeighbor];
};
