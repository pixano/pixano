import type { EditShape, ItemObject, Tracklet, VideoItemBBox, VideoObject } from "@pixano/core";

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
  const [startX, startY, startWidth, startHeight] = start.coords;
  const [endX, endY, endWidth, endHeight] = end.coords;

  const xInterpolation = (endX - startX) / (end.frameIndex - start?.frameIndex);
  const yInterpolation = (endY - startY) / (end.frameIndex - start?.frameIndex);
  const widthInterpolation = (endWidth - startWidth) / (end.frameIndex - start?.frameIndex);
  const heightInterpolation = (endHeight - startHeight) / (end.frameIndex - start?.frameIndex);
  const x = startX + xInterpolation * (imageIndex - start.frameIndex);
  const y = startY + yInterpolation * (imageIndex - start.frameIndex);
  const width = startWidth + widthInterpolation * (imageIndex - start.frameIndex);
  const height = startHeight + heightInterpolation * (imageIndex - start.frameIndex);
  return [x, y, width, height];
};

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  box: VideoItemBBox,
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

export const editKeyBoxInTracklet = (
  objects: ItemObject[],
  boxBeingEdited: VideoItemBBox,
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

const createNewTracklet = (
  track: Tracklet[],
  frameIndex: number,
  lastFrameIndex: number,
  keyBox: VideoItemBBox,
) => {
  let nextIntervalStart = track.find((t) => t.start > frameIndex)?.start;
  nextIntervalStart = nextIntervalStart ? nextIntervalStart - 1 : lastFrameIndex;
  return {
    start: frameIndex,
    end: nextIntervalStart,
    keyBoxes: [
      {
        ...keyBox,
        frameIndex,
      },
      {
        ...keyBox,
        frameIndex: nextIntervalStart,
      },
    ],
  } as Tracklet;
};

const addKeyBoxToTracklet = (track: Tracklet[], tracklet: Tracklet, keyBox: VideoItemBBox) =>
  track.map((trackItem) => {
    if (trackItem.start === tracklet.start && trackItem.end === tracklet.end) {
      trackItem.keyBoxes.push(keyBox);
      trackItem.keyBoxes.sort((a, b) => a.frameIndex - b.frameIndex);
      trackItem.start = trackItem.keyBoxes[0].frameIndex;
      trackItem.end = trackItem.keyBoxes[trackItem.keyBoxes.length - 1].frameIndex;
    }
    return trackItem;
  });

export const addKeyBox = (
  objects: ItemObject[],
  keyBox: VideoItemBBox,
  objectId: string,
  frameIndex: number,
  lastFrameIndex: number,
) => {
  return objects.map((object) => {
    if (objectId !== object.id) return object;
    if (object.datasetItemType !== "video") return object;
    console.log("object.track", object.track);
    const tracklet = object.track.find((t) => t.start <= frameIndex && t.end >= frameIndex);
    if (!tracklet) {
      const newTracklet = createNewTracklet(object.track, frameIndex, lastFrameIndex, keyBox);
      object.track.push(newTracklet);
    } else {
      object.track = addKeyBoxToTracklet(object.track, tracklet, keyBox);
    }
    object.track.sort((a, b) => a.start - b.start);
    return object;
  });
};

export const findNeighbors = (
  track: Tracklet[],
  currentTracklet: Tracklet,
  frameIndex: VideoItemBBox["frameIndex"],
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
  nextNeighbor = nextNeighbor || lastFrameIndex + 1;

  return [prevNeighbor, nextNeighbor];
};

const filterKeyBoxes = (
  keyBoxes: Tracklet["keyBoxes"],
  newBox: VideoItemBBox,
  shouldBeFiltered: (index: VideoItemBBox["frameIndex"]) => boolean,
) =>
  keyBoxes.reduce(
    (acc, box, i) => {
      if (i === 0) {
        acc.push(newBox);
      }
      if (shouldBeFiltered(box.frameIndex)) {
        acc.push(box);
      }
      return acc.sort((a, b) => a.frameIndex - b.frameIndex);
    },
    [] as Tracklet["keyBoxes"],
  );

export const splitTrackletInTwo = (
  object: VideoObject,
  trackletIndex: number,
  rightClickFrameIndex: number,
) => {
  const tracklet = object.track[trackletIndex];
  const startTracklet: Tracklet = {
    start: tracklet.start,
    end: rightClickFrameIndex,
    keyBoxes: filterKeyBoxes(
      tracklet.keyBoxes,
      { ...object.displayedBox, frameIndex: rightClickFrameIndex },
      (index) => index < rightClickFrameIndex,
    ),
  };
  const endTracklet: Tracklet = {
    start: rightClickFrameIndex + 1,
    end: tracklet.end,
    keyBoxes: filterKeyBoxes(
      tracklet.keyBoxes,
      { ...object.displayedBox, frameIndex: rightClickFrameIndex + 1 },
      (index) => index > rightClickFrameIndex + 1,
    ),
  };
  return [
    ...object.track.slice(0, trackletIndex),
    startTracklet,
    endTracklet,
    ...object.track.slice(trackletIndex + 1),
  ];
};
