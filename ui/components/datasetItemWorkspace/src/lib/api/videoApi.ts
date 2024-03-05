import type { BreakPoint, BreakPointInterval, ItemObject } from "@pixano/core";

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
  let left = event.clientX - (node.parentElement?.offsetLeft || 0);
  if (left < 0) left = 0;
  const max = node.parentElement?.offsetWidth || left;
  if (left > max) left = max;
  const index = Math.floor((left / max) * length) - 1;
  return index < 0 ? 0 : index;
};

export const linearInterpolation = (
  breakPointIntervals: BreakPointInterval[],
  imageIndex: number,
) => {
  const currentInterval = breakPointIntervals.find(
    (interval) => interval.start <= imageIndex && interval.end >= imageIndex,
  );
  if (!currentInterval) return [0, 0]; // should be null
  const endIndex = currentInterval.breakPoints.findIndex(
    (breakPoint) => breakPoint.frameIndex > imageIndex,
  );
  const start = currentInterval.breakPoints[endIndex - 1] || currentInterval.breakPoints[0];
  const end = currentInterval.breakPoints[endIndex];
  const { x: startX, y: startY } = start;
  const { x: endX, y: endY } = end;
  const xInterpolation = (endX - startX) / (end.frameIndex - start?.frameIndex);
  const yInterpolation = (endY - startY) / (end.frameIndex - start?.frameIndex);
  const x = startX + xInterpolation * (imageIndex - start.frameIndex);
  const y = startY + yInterpolation * (imageIndex - start.frameIndex);
  return [x, y];
};

export const deleteBreakPointInInterval = (
  objects: ItemObject[],
  breakPoint: BreakPoint,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    if (objectId === object.id && object.bbox?.breakPointsIntervals) {
      object.bbox.breakPointsIntervals = object.bbox.breakPointsIntervals
        .map((interval) => {
          if (interval.start <= breakPoint.frameIndex && interval.end >= breakPoint.frameIndex) {
            interval.breakPoints = interval.breakPoints.filter(
              (bp) => bp.frameIndex !== breakPoint.frameIndex,
            );
            interval.start = interval.breakPoints[0].frameIndex;
            interval.end = interval.breakPoints.at(-1)?.frameIndex || interval.start;
          }
          return interval;
        })
        .filter((interval) => interval.breakPoints.length > 1);
    }
    return object;
  });
