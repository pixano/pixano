import type { BreakPointInterval } from "@pixano/core";

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
  if (!currentInterval || currentInterval.type === "blank") return [0, 0]; // should be null
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
