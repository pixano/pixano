import type { BBoxCoordinate } from "@pixano/core";

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

export const linearInterpolation = (coordinates: BBoxCoordinate[], imageIndex: number) => {
  const nextFrameIndex =
    coordinates?.findIndex((coordinate) => coordinate.frameIndex > imageIndex) || 0;
  const start = coordinates?.[nextFrameIndex - 1] || coordinates?.[0];
  const end = coordinates?.[nextFrameIndex];
  const [startX, startY] = start.coordinates;
  const [endX, endY] = end.coordinates;

  const xInterpolation = (endX - startX) / (end.frameIndex - start?.frameIndex);
  const yInterpolation = (endY - startY) / (end.frameIndex - start?.frameIndex);
  const newX = startX + xInterpolation * (imageIndex - start.frameIndex);
  const newY = startY + yInterpolation * (imageIndex - start.frameIndex);
  return [newX, newY];
};
